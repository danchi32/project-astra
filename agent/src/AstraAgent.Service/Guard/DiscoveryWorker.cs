using System.Diagnostics;
using System.Text.Json;
using AstraAgent.Guard;
using AstraAgent.Service.Api;
using AstraAgent.Service.Enrollment;
using AstraAgent.Service.Security;
using Microsoft.Win32;

namespace AstraAgent.Service.Guard;

/// <summary>
/// Phase 3 · D5: once a week, while the org has the file scan switched on, maps where
/// sensitive files are on this PC and sends the map (folder paths and counts) to the backend.
///
/// The scan itself runs in the native host (<c>savio-guard-host.exe --discover</c>), the process
/// E4 keeps off the network; this service only starts it, reads its one JSON answer, checks it,
/// and sends it on. It looks only in each person's Desktop, Documents, Downloads and OneDrive
/// folders. A run that fails is tried again at the next check; a run that worked is not
/// repeated for a week, across restarts.
/// </summary>
public sealed class DiscoveryWorker(
    BrowserPolicyWorker policy,
    IEnrollmentService enrollment,
    IAstraApiClient api,
    SubscriptionState subscription,
    ILogger<DiscoveryWorker> logger) : BackgroundService
{
    internal static readonly TimeSpan Every = TimeSpan.FromDays(7);
    static readonly TimeSpan Check = TimeSpan.FromMinutes(30);
    static readonly TimeSpan FirstWait = TimeSpan.FromMinutes(10);
    static readonly TimeSpan MaxRun = TimeSpan.FromHours(3);

    internal Func<BrowserPolicy?> Policy { get; init; } = () => policy.Current;
    internal Func<IReadOnlyList<string>> Roots { get; init; } = UserFolders;
    internal Func<IReadOnlyList<string>, CancellationToken, Task<DiscoveryReport?>> Scan { get; init; } = RunHostAsync;
    internal string LastRunFile { get; init; } = Path.Combine(SecureDirectory.StateRoot, "discovery-last.txt");

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        try { await Task.Delay(FirstWait, stoppingToken); } catch (OperationCanceledException) { return; }
        while (!stoppingToken.IsCancellationRequested)
        {
            try { await RunOnceAsync(DateTime.UtcNow, stoppingToken); }
            catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested) { break; }
            catch (Exception ex) { logger.LogError(ex, "File discovery failed"); }
            try { await Task.Delay(Check, stoppingToken); } catch (OperationCanceledException) { break; }
        }
    }

    /// <summary>True when a scan ran and its map was accepted.</summary>
    internal async Task<bool> RunOnceAsync(DateTime nowUtc, CancellationToken ct)
    {
        if (subscription.Dormant || Policy()?.DiscoveryEnabled != true) return false;
        if (LastRun() is { } last && nowUtc - last < Every) return false;
        var token = await enrollment.GetDeviceTokenAsync(ct);
        if (token is null) return false;

        var roots = Roots();
        var report = await Scan(roots, ct);
        if (report is null || !Valid(report, roots))
        {
            logger.LogWarning("File discovery gave no usable result");
            return false;
        }
        if (!await api.SendDiscoveryAsync(token, nowUtc, report, ct)) return false;
        try
        {
            if (LastRunFile.StartsWith(SecureDirectory.StateRoot, StringComparison.OrdinalIgnoreCase))
                SecureDirectory.Ensure(SecureDirectory.StateRoot);
            File.WriteAllText(LastRunFile, nowUtc.ToString("O"));
        }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException) { }
        logger.LogInformation("File discovery: {Files} files read, {Folders} folders with findings",
                              report.FilesScanned, report.Folders.Count);
        return true;
    }

    DateTime? LastRun()
    {
        try
        {
            return File.Exists(LastRunFile) && DateTime.TryParse(File.ReadAllText(LastRunFile), null,
                       System.Globalization.DateTimeStyles.RoundtripKind, out var t) ? t.ToUniversalTime() : null;
        }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException) { return null; }
    }

    /// <summary>The host's answer is checked like anything else crossing a boundary: every
    /// folder must be inside a folder it was asked to look at, and counts only of known kinds.</summary>
    internal static bool Valid(DiscoveryReport r, IReadOnlyList<string> roots) =>
        r.Ok && r.Folders.Count <= 500 && r.FilesScanned >= 0 && r.FilesSkipped >= 0 &&
        r.Folders.All(f =>
            f.Path.Length <= 400 && f.Path.IndexOfAny(['\r', '\n', '\0']) < 0 &&
            roots.Any(root => f.Path.Equals(root, StringComparison.OrdinalIgnoreCase) ||
                              f.Path.StartsWith(root.TrimEnd('\\') + "\\", StringComparison.OrdinalIgnoreCase)) &&
            f.Files >= f.FilesWithFindings && f.FilesWithFindings >= 0 && f.ContactLists >= 0 &&
            f.Counts.All(kv => GuardEvent.Kinds.Contains(kv.Key) && kv.Value >= 0));

    static async Task<DiscoveryReport?> RunHostAsync(IReadOnlyList<string> roots, CancellationToken ct)
    {
        var exe = Path.Combine(AppContext.BaseDirectory, NativeHostRegistration.HostExe);
        if (!File.Exists(exe) || roots.Count == 0) return null;
        var psi = new ProcessStartInfo(exe) { UseShellExecute = false, RedirectStandardOutput = true, CreateNoWindow = true };
        psi.ArgumentList.Add("--discover");
        foreach (var r in roots) psi.ArgumentList.Add(r);
        using var p = Process.Start(psi);
        if (p is null) return null;
        using var timeout = CancellationTokenSource.CreateLinkedTokenSource(ct);
        timeout.CancelAfter(MaxRun);
        try
        {
            var output = await p.StandardOutput.ReadToEndAsync(timeout.Token);
            await p.WaitForExitAsync(timeout.Token);
            return p.ExitCode == 0 ? JsonSerializer.Deserialize<DiscoveryReport>(output) : null;
        }
        catch (Exception ex) when (ex is OperationCanceledException or JsonException)
        {
            try { p.Kill(entireProcessTree: true); } catch { /* already gone */ }
            if (ct.IsCancellationRequested) throw;
            return null;
        }
    }

    /// <summary>Desktop, Documents, Downloads and OneDrive folders of every real account on this PC.</summary>
    static IReadOnlyList<string> UserFolders()
    {
        var roots = new List<string>();
        using var list = Registry.LocalMachine.OpenSubKey(@"SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList");
        foreach (var sid in list?.GetSubKeyNames() ?? [])
        {
            if (!sid.StartsWith("S-1-5-21-", StringComparison.Ordinal)) continue;   // people, not service accounts
            using var key = list!.OpenSubKey(sid);
            if (key?.GetValue("ProfileImagePath") is not string profile || !Directory.Exists(profile)) continue;
            foreach (var name in new[] { "Desktop", "Documents", "Downloads" })
                if (Directory.Exists(Path.Combine(profile, name))) roots.Add(Path.Combine(profile, name));
            try
            {
                roots.AddRange(Directory.EnumerateDirectories(profile, "OneDrive*"));
            }
            catch (Exception ex) when (ex is IOException or UnauthorizedAccessException) { }
        }
        return roots;
    }
}
