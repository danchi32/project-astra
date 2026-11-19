using System.Collections.Concurrent;
using System.Diagnostics;
using System.Text.Json;
using AstraAgent.Guard;
using AstraAgent.Service.Api;
using AstraAgent.Service.Enrollment;

namespace AstraAgent.Service.Guard;

/// <summary>What the scanner found in a batch of copied files (the host's <c>--scan</c> answer).</summary>
public sealed record UsbScanResult(int Files, int Unreadable, Dictionary<string, int> Counts, bool ContactList, int KeywordHits);

/// <summary>
/// Phase 3c · C3b: what is copied onto USB drives, where the org asks (<c>usb_observe</c>).
///
/// Every few seconds the service lists removable drives and watches each one for files written
/// to it. A file is checked once it has been quiet for <see cref="Settle"/> (the copy is done),
/// by the native host (<c>--scan</c>), the process E4 keeps off the network, in batches. What is
/// recorded is one event per batch, like the browser's: channel and site "usb", counts per kind,
/// the contact-list flag, keyword hits, and "could not check" for documents it cannot read. The
/// person is the one signed in at the console. No file names, no paths, no text.
///
/// It sees, it does not stop: a copy is already on the drive when it is checked. Stopping is the
/// USB mode's job (read-only, encrypted only, write windows).
/// ponytail: the console user, not the copying process's owner. A copy made over RDP by another
/// account is credited to whoever is at the console. Upgrade path: the writing process's token
/// from an ETW file trace.
/// </summary>
public sealed class UsbCopyWatcher(
    BrowserPolicyWorker policy,
    GuardEventQueue queue,
    SubscriptionState subscription,
    ILogger<UsbCopyWatcher> logger) : BackgroundService
{
    internal static readonly TimeSpan Settle = TimeSpan.FromSeconds(5);
    static readonly TimeSpan Tick = TimeSpan.FromSeconds(3);

    /// <summary>The real drive list, scanner and console user. Tests replace them.</summary>
    internal Func<IReadOnlyList<string>> Drives { get; init; } = RemovableDrives;
    internal Func<IReadOnlyList<string>, BrowserPolicy, UsbScanResult?> Scan { get; init; } = RunHost;
    internal Func<string?> User { get; init; } = LoggedInUserResolver.GetConsoleUser;
    internal Func<BrowserPolicy?> Policy { get; init; } = () => policy.Current;

    readonly Dictionary<string, FileSystemWatcher> _watchers = new(StringComparer.OrdinalIgnoreCase);
    readonly ConcurrentDictionary<string, DateTime> _pending = new(StringComparer.OrdinalIgnoreCase);

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        while (!stoppingToken.IsCancellationRequested)
        {
            try { Cycle(DateTime.UtcNow); }
            catch (Exception ex) { logger.LogError(ex, "Watching USB copies failed"); }
            try { await Task.Delay(Tick, stoppingToken); } catch (OperationCanceledException) { break; }
        }
        foreach (var w in _watchers.Values) w.Dispose();
    }

    internal void Cycle(DateTime nowUtc)
    {
        var p = Policy();
        var on = !subscription.Dormant && p is { UsbObserve: true };
        Watch(on ? Drives() : []);
        if (on) Flush(nowUtc, p!);
        else _pending.Clear();
    }

    /// <summary>Something was written to a drive: (re)start its quiet period.</summary>
    internal void Written(string path, DateTime nowUtc) => _pending[path] = nowUtc;

    /// <summary>Files quiet for long enough are checked, as one batch, and recorded if anything
    /// in them matters.</summary>
    internal void Flush(DateTime nowUtc, BrowserPolicy p)
    {
        var ready = _pending.Where(kv => nowUtc - kv.Value >= Settle).Select(kv => kv.Key).Take(FileScanLimit).ToList();
        if (ready.Count == 0) return;
        foreach (var path in ready) _pending.TryRemove(path, out _);
        var r = Scan(ready, p);
        if (r is null) return;
        var e = new GuardEvent("usb", "usb", "log", "allow", r.Counts, r.ContactList, r.KeywordHits,
                               Unknown: r.Unreadable > 0);
        if (!e.Notable || !e.IsValid()) return;
        var user = User();
        if (string.IsNullOrEmpty(user)) return;   // nobody at the console: cannot be attributed
        if (!queue.TryAdd(new QueuedGuardEvent(nowUtc, user, e)))
            logger.LogWarning("A USB copy event was dropped (rate or queue limit)");
    }

    internal const int FileScanLimit = 200;

    void Watch(IReadOnlyList<string> roots)
    {
        foreach (var gone in _watchers.Keys.Except(roots, StringComparer.OrdinalIgnoreCase).ToList())
        {
            _watchers[gone].Dispose();
            _watchers.Remove(gone);
        }
        foreach (var root in roots.Where(r => !_watchers.ContainsKey(r)))
        {
            try
            {
                var w = new FileSystemWatcher(root)
                {
                    IncludeSubdirectories = true,
                    NotifyFilter = NotifyFilters.FileName | NotifyFilters.Size | NotifyFilters.LastWrite,
                    InternalBufferSize = 64 * 1024,
                };
                w.Created += (_, a) => Written(a.FullPath, DateTime.UtcNow);
                w.Changed += (_, a) => Written(a.FullPath, DateTime.UtcNow);
                w.Renamed += (_, a) => Written(a.FullPath, DateTime.UtcNow);
                w.EnableRaisingEvents = true;
                _watchers[root] = w;
            }
            catch (Exception ex) when (ex is ArgumentException or IOException or UnauthorizedAccessException)
            {
                logger.LogDebug(ex, "Could not watch {Drive}", root);
            }
        }
    }

    static IReadOnlyList<string> RemovableDrives()
    {
        try
        {
            return DriveInfo.GetDrives().Where(d => d.DriveType == DriveType.Removable && d.IsReady)
                            .Select(d => d.RootDirectory.FullName).ToList();
        }
        catch (IOException) { return []; }
    }

    static readonly JsonSerializerOptions Json = new() { PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower };

    /// <summary>The host's <c>--scan</c>: paths and keywords in on stdin, one total out.</summary>
    static UsbScanResult? RunHost(IReadOnlyList<string> paths, BrowserPolicy p)
    {
        var exe = Path.Combine(AppContext.BaseDirectory, NativeHostRegistration.HostExe);
        if (!File.Exists(exe)) return null;
        var psi = new ProcessStartInfo(exe)
        {
            UseShellExecute = false, RedirectStandardInput = true, RedirectStandardOutput = true, CreateNoWindow = true,
        };
        psi.ArgumentList.Add("--scan");
        using var proc = Process.Start(psi);
        if (proc is null) return null;
        proc.StandardInput.Write(JsonSerializer.Serialize(new { paths, keywords = p.GuardKeywords, pdf = p.ReadPdfs }, Json));
        proc.StandardInput.Close();
        var output = proc.StandardOutput.ReadToEndAsync();
        if (!proc.WaitForExit(60_000))
        {
            try { proc.Kill(entireProcessTree: true); } catch { /* already gone */ }
            return null;
        }
        try { return proc.ExitCode == 0 ? JsonSerializer.Deserialize<UsbScanResult>(output.Result, Json) : null; }
        catch (JsonException) { return null; }
    }
}
