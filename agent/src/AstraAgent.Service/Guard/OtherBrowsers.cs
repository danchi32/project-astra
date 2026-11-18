using System.ComponentModel;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text;
using AstraAgent.Service.Api;
using AstraAgent.Service.Sessions;

namespace AstraAgent.Service.Guard;

/// <summary>
/// Phase 3 · D10: browsers SAVIO's policies and extension do not reach. Anyone who wants to get
/// round the blocked sites, the company-account rules or the paste checks only has to open one.
/// Supported browsers are Chrome, Edge and Firefox.
///
/// A process is one of these only if its exe name matches AND the browser's own name appears in
/// the file's company, product or path, so an unrelated <c>browser.exe</c> or a Google Chrome
/// is never touched. A process whose file cannot be read is left alone.
/// </summary>
public static class OtherBrowsers
{
    /// <summary>Exe name, a marker that must appear in its company, product or path, and the
    /// name reported. The names are the backend's OTHER_BROWSERS; the two lists change together.</summary>
    internal static readonly (string Exe, string Marker, string Name)[] Known =
    [
        ("brave", "Brave", "Brave"),
        ("opera", "Opera", "Opera"),                    // Opera and Opera GX
        ("vivaldi", "Vivaldi", "Vivaldi"),
        ("browser", "Yandex", "Yandex Browser"),
        ("firefox", "Tor Browser", "Tor Browser"),      // Tor Browser ships its own firefox.exe
        ("chrome", "Chromium", "Chromium"),             // reads Chromium's policies, not Chrome's
        ("waterfox", "Waterfox", "Waterfox"),
        ("librewolf", "LibreWolf", "LibreWolf"),
    ];

    /// <summary>The reported name, or null if this process is not one of them.</summary>
    public static string? Match(string processName, string? company, string? product, string? path)
    {
        var seen = $"{company}|{product}|{path}";
        foreach (var (exe, marker, name) in Known)
            if (string.Equals(processName, exe, StringComparison.OrdinalIgnoreCase) &&
                seen.Contains(marker, StringComparison.OrdinalIgnoreCase))
                return name;
        return null;
    }

    internal static bool MaybeOne(string processName) =>
        Known.Any(k => string.Equals(processName, k.Exe, StringComparison.OrdinalIgnoreCase));
}

/// <summary>A running process, as far as <see cref="OtherBrowserBlocker"/> needs one.</summary>
public sealed record RunningProcess(int Id, int Session, string Name, string? Company, string? Product, string? Path);

/// <summary>
/// Phase 3 · D10: where the org's policy says so, closes any of <see cref="OtherBrowsers"/> within
/// two seconds of it starting, and tells the person why and what to use instead (at most once a
/// minute per browser and session). The number of times is reported with the next browser-policy
/// report, and the backend audits it.
///
/// Closing is all it does. Removing the browser is the admin-only "Uninstall software" action,
/// decided by a person, PC by PC. A local admin can stop the service, as they can undo any policy.
/// </summary>
public sealed class OtherBrowserBlocker(
    BrowserPolicyWorker policy,
    SubscriptionState subscription,
    ILogger<OtherBrowserBlocker> logger) : BackgroundService
{
    internal static readonly TimeSpan Interval = TimeSpan.FromSeconds(2);
    internal static readonly TimeSpan NoticeEvery = TimeSpan.FromMinutes(1);

    /// <summary>The real process list, kill and notice. Tests replace them.</summary>
    internal Func<IEnumerable<RunningProcess>> List { get; init; } = Candidates;
    internal Func<int, bool> Kill { get; init; } = KillProcess;
    internal Action<int, string> Notify { get; init; } = ShowNotice;

    readonly Dictionary<(int Session, string Name), DateTime> _noticed = [];

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        while (!stoppingToken.IsCancellationRequested)
        {
            try { Sweep(DateTime.UtcNow); }
            catch (Exception ex) { logger.LogError(ex, "Closing other browsers failed"); }
            try { await Task.Delay(Interval, stoppingToken); }
            catch (OperationCanceledException) { break; }
        }
    }

    internal void Sweep(DateTime nowUtc)
    {
        if (subscription.Dormant || policy.Current is not { BlockOtherBrowsers: true })
            return;
        var closed = new HashSet<(int Session, string Name)>();
        foreach (var p in List())
        {
            if (OtherBrowsers.Match(p.Name, p.Company, p.Product, p.Path) is { } name && Kill(p.Id))
                closed.Add((p.Session, name));
        }
        // One start of a browser is many processes: counted once per session and sweep.
        foreach (var (session, name) in closed)
        {
            policy.CountClosed(name);
            logger.LogInformation("Closed {Browser} in session {Session}: the org's browser policy does not allow it",
                                  name, session);
            if (_noticed.TryGetValue((session, name), out var last) && nowUtc - last < NoticeEvery)
                continue;
            _noticed[(session, name)] = nowUtc;
            Notify(session, name);
        }
    }

    static IEnumerable<RunningProcess> Candidates()
    {
        foreach (var p in Process.GetProcesses())
        {
            using (p)
            {
                if (!OtherBrowsers.MaybeOne(p.ProcessName))
                    continue;
                RunningProcess? r = null;
                try
                {
                    var path = ImagePath(p.Id);
                    var info = path is null ? null : FileVersionInfo.GetVersionInfo(path);
                    r = new RunningProcess(p.Id, p.SessionId, p.ProcessName, info?.CompanyName, info?.ProductName, path);
                }
                catch (Exception ex) when (ex is InvalidOperationException or Win32Exception or IOException) { }   // gone, or unreadable: left alone
                if (r is not null)
                    yield return r;
            }
        }
    }

    static bool KillProcess(int id)
    {
        try
        {
            using var p = Process.GetProcessById(id);
            p.Kill();
            return true;
        }
        catch (Exception ex) when (ex is ArgumentException or InvalidOperationException or Win32Exception or NotSupportedException)
        {
            return false;   // already gone, or not ours to close
        }
    }

    static void ShowNotice(int session, string name)
    {
        const string title = "SAVIO";
        var text = $"{name} is not allowed on this PC by your organization, so it was closed.\n\n"
                 + "Please use Google Chrome, Microsoft Edge or Firefox.";
        // bWait: false, so a person away from the desk holds nothing up.
        WtsNative.WTSSendMessage(IntPtr.Zero, session, title, title.Length * 2, text, text.Length * 2,
                                 0x40 /* MB_ICONINFORMATION */, 60, out _, false);
    }

    static string? ImagePath(int pid)
    {
        var h = OpenProcess(0x1000 /* PROCESS_QUERY_LIMITED_INFORMATION */, false, pid);
        if (h == IntPtr.Zero) return null;
        try
        {
            var size = 1024;
            var buffer = new StringBuilder(size);
            return QueryFullProcessImageName(h, 0, buffer, ref size) ? buffer.ToString() : null;
        }
        finally { CloseHandle(h); }
    }

    [DllImport("kernel32.dll", SetLastError = true)]
    static extern IntPtr OpenProcess(uint access, bool inherit, int processId);
    [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    static extern bool QueryFullProcessImageName(IntPtr process, int flags, StringBuilder name, ref int size);
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern bool CloseHandle(IntPtr handle);
}
