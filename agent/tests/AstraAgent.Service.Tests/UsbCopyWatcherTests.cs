using System.Text.Json;
using AstraAgent.GuardHost;
using AstraAgent.Service.Api;
using AstraAgent.Service.Guard;
using Microsoft.Extensions.Logging.Abstractions;
using Microsoft.Extensions.Options;
using Xunit;

namespace AstraAgent.Service.Tests;

/// <summary>
/// Phase 3c · C3b: files copied to USB drives are checked once the copy settles, by the isolated
/// scanner, and recorded as one event of counts: no names, no paths, no text. Only where the org
/// asks. The drive list, the scanner process and the console user are replaced here.
/// </summary>
public sealed class UsbCopyWatcherTests : IDisposable
{
    readonly string _dir = Path.Combine(Path.GetTempPath(), "savio-usb-" + Guid.NewGuid().ToString("N"));

    public void Dispose()
    {
        if (Directory.Exists(_dir)) Directory.Delete(_dir, true);
    }

    [Fact]
    public void The_scanner_totals_the_files_and_names_none_of_them()
    {
        Directory.CreateDirectory(_dir);
        var rows = string.Join("\n", Enumerable.Range(0, 30).Select(i => $"Client {i},+91 98765{i:00000},c{i}@example.com"));
        File.WriteAllText(Path.Combine(_dir, "clients.csv"),
            "name,email,phone\n" + rows + "\nAsha,ABCPE1234F,x\nRavi,BCDPF2345G,y\n");
        File.WriteAllText(Path.Combine(_dir, "notes.txt"), "Project falcon notes");
        File.WriteAllText(Path.Combine(_dir, "backup.zip"), "PK not really");      // a document it cannot read
        File.WriteAllText(Path.Combine(_dir, "photo.jpg"), "ABCPE1234F");          // not a document at all
        var paths = Directory.GetFiles(_dir);

        var r = FileScan.Run(new FileScan.Request(paths, ["project falcon"]));
        Assert.Equal((2, 1), (r.Files, r.Unreadable));
        Assert.Equal(2, r.Counts["Pan"]);
        Assert.True(r.ContactList);
        Assert.Equal(1, r.KeywordHits);
        var json = JsonSerializer.Serialize(r);
        foreach (var leak in new[] { "clients", "ABCPE1234F", "Asha", _dir }) Assert.DoesNotContain(leak, json);
    }

    readonly GuardEventQueue _queue = new();
    readonly SubscriptionState _subscription = new();
    readonly List<IReadOnlyList<string>> _scanned = [];
    UsbScanResult? _result = new(1, 0, new() { ["Pan"] = 230 }, false, 0);
    BrowserPolicy? _policy = new() { UsbObserve = true };

    UsbCopyWatcher Watcher() => new(null!, _queue, _subscription, NullLogger<UsbCopyWatcher>.Instance)
    {
        Drives = () => [],
        Scan = (paths, _) => { _scanned.Add(paths); return _result; },
        User = () => @"ACME\ravi",
        Policy = () => _policy,
    };

    [Fact]
    public void A_copy_is_checked_once_it_settles_and_recorded_as_counts()
    {
        var w = Watcher();
        var t0 = new DateTime(2026, 11, 19, 10, 0, 0, DateTimeKind.Utc);
        w.Written(@"E:\clients.csv", t0);
        w.Written(@"E:\more\list.xlsx", t0.AddSeconds(1));
        w.Cycle(t0.AddSeconds(3));
        Assert.Empty(_scanned);                                            // still being written
        w.Written(@"E:\clients.csv", t0.AddSeconds(4));                    // the copy goes on
        w.Cycle(t0.AddSeconds(7));
        Assert.Equal([@"E:\more\list.xlsx"], _scanned.Single());           // only what has settled
        w.Cycle(t0.AddSeconds(10));
        Assert.Equal([@"E:\clients.csv"], _scanned[1]);

        var events = _queue.Peek(10);
        Assert.Equal(2, events.Count);
        var e = events[0];
        Assert.Equal(("usb", "usb", @"ACME\ravi", 230), (e.Event.Site, e.Event.Channel, e.WindowsUser, e.Event.Counts["Pan"]));
        Assert.DoesNotContain("clients", JsonSerializer.Serialize(e.Event));
    }

    [Fact]
    public void Nothing_found_nobody_signed_in_or_not_asked_for_is_not_recorded()
    {
        var w = Watcher();
        var t0 = new DateTime(2026, 11, 19, 10, 0, 0, DateTimeKind.Utc);
        _result = new(3, 0, [], false, 0);                                 // clean files
        w.Written(@"E:\a.txt", t0);
        w.Cycle(t0.AddSeconds(6));
        Assert.Equal(0, _queue.Count);

        _result = new(0, 2, [], false, 0);                                 // archives: "could not check"
        w.Written(@"E:\b.zip", t0);
        w.Cycle(t0.AddSeconds(12));
        Assert.True(_queue.Peek(1).Single().Event.Unknown);

        _policy = new BrowserPolicy();                                     // the org does not ask
        w.Written(@"E:\c.txt", t0.AddSeconds(12));
        w.Cycle(t0.AddSeconds(20));
        Assert.Equal(2, _scanned.Count);                                   // not checked at all
    }
}
