using System.IO.Compression;
using System.Text;
using System.Text.Json;
using AstraAgent.GuardHost;
using AstraAgent.Service.Api;
using AstraAgent.Service.Guard;
using Microsoft.Extensions.Logging.Abstractions;
using Microsoft.Extensions.Options;
using Xunit;

namespace AstraAgent.Service.Tests;

/// <summary>
/// Phase 3 · D5: the file scan (in the native host) and the weekly worker (in the service).
/// The scan reads what it should, skips what it must not open, and reports folders and counts,
/// never file names or text. Runs on a temp folder tree.
/// </summary>
public sealed class DiscoveryTests : IDisposable
{
    readonly string _root = Path.Combine(Path.GetTempPath(), "savio-d5-" + Guid.NewGuid().ToString("N"));

    public void Dispose()
    {
        if (!Directory.Exists(_root)) return;
        // Remove junctions first, so deleting the tree never walks through one.
        foreach (var d in Directory.EnumerateDirectories(_root, "*", SearchOption.AllDirectories)
                     .Where(d => new DirectoryInfo(d).Attributes.HasFlag(FileAttributes.ReparsePoint)).ToList())
            Directory.Delete(d);
        foreach (var f in Directory.EnumerateFiles(_root, "*", SearchOption.AllDirectories))
            File.SetAttributes(f, FileAttributes.Normal);
        Directory.Delete(_root, true);
    }

    string Docs => Path.Combine(_root, "Documents");

    static void Zip(string path, string entry, string xml)
    {
        using var zip = ZipFile.Open(path, ZipArchiveMode.Create);
        using var w = new StreamWriter(zip.CreateEntry(entry).Open());
        w.Write(xml);
    }

    void Tree()
    {
        var clients = Path.Combine(Docs, "Clients");
        Directory.CreateDirectory(clients);
        File.WriteAllText(Path.Combine(clients, "kyc.csv"), "name,pan,phone\nAsha,ABCPE1234F,+91 98765 43210\nRavi,BCDPF2345G,9876501234\n");
        File.WriteAllText(Path.Combine(Docs, "notes.txt"), "Lunch at 1, nothing else.");
        Zip(Path.Combine(Docs, "letter.docx"), "word/document.xml",
            "<w:document><w:body><w:p><w:t>PAN of director: ABCPE1234F</w:t></w:p></w:body></w:document>");
        Zip(Path.Combine(Docs, "sheet.xlsx"), "xl/sharedStrings.xml",
            "<sst><si><t>Card 4111 1111 1111 1111</t></si></sst>");
        File.WriteAllText(Path.Combine(Docs, "fake.docx"), "not a zip");                     // skipped, not fatal
        File.WriteAllText(Path.Combine(Docs, "photo.jpg"), "ABCPE1234F");                    // not a type we read

        var hidden = Path.Combine(Docs, "hidden.txt");
        File.WriteAllText(hidden, "ABCPE1234F");
        File.SetAttributes(hidden, FileAttributes.Hidden);
        var cloud = Path.Combine(Docs, "cloud-only.txt");                                    // a OneDrive placeholder
        File.WriteAllText(cloud, "ABCPE1234F");
        File.SetAttributes(cloud, FileAttributes.Offline);
        foreach (var skip in new[] { "AppData", ".git", "node_modules" })
        {
            Directory.CreateDirectory(Path.Combine(Docs, skip));
            File.WriteAllText(Path.Combine(Docs, skip, "x.txt"), "ABCPE1234F");
        }
    }

    [Fact]
    public void Maps_folders_with_counts_and_nothing_else()
    {
        Tree();
        var r = Discovery.Run([Docs], TimeSpan.Zero);
        Assert.True(r.Ok);
        Assert.Equal(4, r.FilesScanned);                       // kyc.csv, notes.txt, letter.docx, sheet.xlsx
        Assert.Equal(1, r.FilesSkipped);                       // fake.docx
        Assert.Equal(2, r.Folders.Count);                      // only folders with findings

        var clients = r.Folders.Single(f => f.Path.EndsWith("Clients"));
        Assert.Equal(2, clients.Counts["Pan"]);
        Assert.Equal(2, clients.Counts["IndianMobile"]);
        var docs = r.Folders.Single(f => f.Path == Docs);
        Assert.Equal(3, docs.Files);
        Assert.Equal(2, docs.FilesWithFindings);               // the letter and the sheet
        Assert.Equal(1, docs.Counts["Pan"]);
        Assert.Equal(1, docs.Counts["PaymentCard"]);

        var json = JsonSerializer.Serialize(r);
        foreach (var leak in new[] { "ABCPE1234F", "kyc.csv", "letter.docx", "Asha", "98765" })
            Assert.DoesNotContain(leak, json);
    }

    [Fact]
    public void Junctions_are_never_followed_and_folder_names_are_redacted()
    {
        Tree();
        // Review M1: a junction a user planted, here to a folder outside the asked ones.
        var outside = Path.Combine(_root, "Elsewhere");
        Directory.CreateDirectory(outside);
        File.WriteAllText(Path.Combine(outside, "secret.csv"), "pan\nABCPE1234F\n");
        // A junction, as any standard user can make one (a symlink would need a privilege).
        using (var mk = System.Diagnostics.Process.Start(new System.Diagnostics.ProcessStartInfo("cmd.exe",
                   $"/c mklink /J \"{Path.Combine(Docs, "link")}\" \"{outside}\"") { CreateNoWindow = true, UseShellExecute = false }))
            mk!.WaitForExit();
        Assert.True(new DirectoryInfo(Path.Combine(Docs, "link")).Attributes.HasFlag(FileAttributes.ReparsePoint));
        // Review M3: a folder name that is itself sensitive.
        var named = Path.Combine(Docs, "Rahul ABCPE1234F");
        Directory.CreateDirectory(named);
        File.WriteAllText(Path.Combine(named, "a.csv"), "pan\nBCDPF2345G\n");

        var r = Discovery.Run([Docs], TimeSpan.Zero);
        Assert.DoesNotContain(r.Folders, f => f.Path.Contains("Elsewhere") || f.Path.EndsWith("link"));
        var folder = Assert.Single(r.Folders, f => f.Path.Contains("Rahul"));
        Assert.Equal(Path.Combine(Docs, "Rahul [PAN]"), folder.Path);
        Assert.DoesNotContain("ABCPE1234F", JsonSerializer.Serialize(r));

        // A root that is itself a link is not followed either.
        Assert.Empty(Discovery.Run([Path.Combine(Docs, "link")], TimeSpan.Zero).Folders);
    }

    [Fact]
    public void A_zip_bomb_or_huge_file_is_skipped_by_its_size()
    {
        Directory.CreateDirectory(Docs);
        var big = Path.Combine(Docs, "huge.txt");
        using (var f = File.Create(big)) f.SetLength(Discovery.MaxFileBytes + 1);
        Assert.Null(Discovery.Text(big, ".txt"));
        var r = Discovery.Run([Docs], TimeSpan.Zero);
        Assert.Equal(1, r.FilesSkipped);
    }

    // ── the service's weekly worker ──────────────────────────────────────────────────────

    sealed class Clock { public DateTime Now = new(2026, 11, 17, 9, 0, 0, DateTimeKind.Utc); }

    (DiscoveryWorker Worker, BrowserPolicyWorkerTests.Api Api, List<int> Scans) Worker(bool enabled, DiscoveryReport? report = null)
    {
        var api = new BrowserPolicyWorkerTests.Api();
        var enrollment = new BrowserPolicyWorkerTests.Enrollment();
        var policyWorker = new BrowserPolicyWorker(enrollment, api, new SubscriptionState(),
            Options.Create(new AgentOptions()), NullLogger<BrowserPolicyWorker>.Instance);
        var scans = new List<int>();
        report ??= new DiscoveryReport(true, 10, 0, false,
            [new DiscoveryFolder(Path.Combine(Docs, "Clients"), 3, 1, new() { ["Pan"] = 2 }, 0)]);
        var w = new DiscoveryWorker(policyWorker, enrollment, api, new SubscriptionState(), NullLogger<DiscoveryWorker>.Instance)
        {
            Policy = () => new BrowserPolicy { DiscoveryEnabled = enabled },
            Roots = () => [Docs],
            Scan = (_, _) => { scans.Add(1); return Task.FromResult<DiscoveryReport?>(report); },
            LastRunFile = Path.Combine(_root, "discovery-last.txt"),
        };
        Directory.CreateDirectory(_root);
        return (w, api, scans);
    }

    [Fact]
    public async Task Runs_weekly_only_when_switched_on()
    {
        var t = new DateTime(2026, 11, 17, 9, 0, 0, DateTimeKind.Utc);
        var (off, offApi, offScans) = Worker(enabled: false);
        Assert.False(await off.RunOnceAsync(t, default));
        Assert.Empty(offScans);

        var (w, api, scans) = Worker(enabled: true);
        Assert.True(await w.RunOnceAsync(t, default));
        Assert.Single(api.Discoveries);
        Assert.False(await w.RunOnceAsync(t.AddDays(3), default));                       // not before a week
        Assert.Single(scans);
        Assert.True(await w.RunOnceAsync(t.AddDays(7).AddMinutes(1), default));
    }

    [Fact]
    public async Task A_map_that_does_not_fit_is_not_sent()
    {
        var t = new DateTime(2026, 11, 17, 9, 0, 0, DateTimeKind.Utc);
        var outside = new DiscoveryReport(true, 1, 0, false,
            [new DiscoveryFolder(@"C:\Windows\System32", 1, 1, new() { ["Pan"] = 1 }, 0)]);
        var (w1, api1, _) = Worker(enabled: true, outside);
        Assert.False(await w1.RunOnceAsync(t, default));
        Assert.Empty(api1.Discoveries);

        var unknownKind = new DiscoveryReport(true, 1, 0, false,
            [new DiscoveryFolder(Docs, 1, 1, new() { ["Passwords"] = 1 }, 0)]);
        var (w2, api2, _) = Worker(enabled: true, unknownKind);
        Assert.False(await w2.RunOnceAsync(t, default));
        Assert.Empty(api2.Discoveries);

        var (w3, api3, scans3) = Worker(enabled: true);
        api3.DiscoveryAccepted = false;                                                  // backend down
        Assert.False(await w3.RunOnceAsync(t, default));
        api3.DiscoveryAccepted = true;
        Assert.True(await w3.RunOnceAsync(t.AddMinutes(30), default));                   // tried again, not a week later
        Assert.Equal(2, scans3.Count);
    }
}
