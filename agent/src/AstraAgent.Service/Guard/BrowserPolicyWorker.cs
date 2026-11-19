using AstraAgent.Service.Api;
using AstraAgent.Service.Enrollment;
using Microsoft.Extensions.Options;

namespace AstraAgent.Service.Guard;

/// <summary>
/// Phase 3 · D10: keeps this PC's browser policy in line with what the org set.
///
/// The policy is fetched hourly and applied every heartbeat cycle. Applying is a handful of
/// registry reads when nothing has changed, and a lock that a local admin removes comes back
/// within a minute instead of an hour. A report goes to the backend when the apply changed
/// something (set, repaired, removed), or when the version, conflicts or errors differ from
/// the last report.
///
/// What it never does is take a policy *away* because the backend could not be reached: a
/// failed fetch keeps the last policy. Only an answer of "version 0, empty" removes
/// everything, and that answer means the org turned AI Guard off.
/// </summary>
public sealed class BrowserPolicyWorker(
    IEnrollmentService enrollment,
    IAstraApiClient api,
    SubscriptionState subscription,
    IOptions<AgentOptions> options,
    ILogger<BrowserPolicyWorker> logger) : BackgroundService
{
    internal static readonly TimeSpan FetchInterval = TimeSpan.FromHours(1);
    internal static readonly TimeSpan RetryAfterFailure = TimeSpan.FromMinutes(5);

    /// <summary>The real writer. Tests replace it, so they never touch HKLM.</summary>
    internal Func<BrowserPolicy, IReadOnlyList<ApplyReport>> Apply { get; init; } = BrowserPolicyWriter.Apply;

    /// <summary>C3b: the USB drives Windows has installed here. Tests replace it.</summary>
    internal Func<IReadOnlyList<SeenDrive>> Drives { get; init; } =
        () => BrowserPolicyWriter.SeenDrives(Microsoft.Win32.Registry.LocalMachine);

    /// <summary>D7: where approvals go for the native host. Tests replace it.</summary>
    internal Action<IReadOnlyList<AgentGuardApproval>> StoreApprovals { get; init; } = GuardApprovalStore.WriteMachine;

    private AgentBrowserPolicy? _current;

    /// <summary>The policy last fetched, for the other AI Guard workers (D5). Null until the
    /// backend has answered once.</summary>
    public BrowserPolicy? Current => _current?.Policy.ToPolicy();

    /// <summary>Other browsers closed since the last report that reached the backend.</summary>
    readonly System.Collections.Concurrent.ConcurrentDictionary<string, int> _closed = new();

    /// <summary>Called by <see cref="OtherBrowserBlocker"/>; sent with the next report.</summary>
    public void CountClosed(string browser) => _closed.AddOrUpdate(browser, 1, (_, n) => n + 1);

    private bool _approvalsMayBeStored = true;   // from a previous run, until the first cycle clears them
    private DateTime? _usbWriteUntil;
    private string? _currentFor;
    private DateTime _nextFetch = DateTime.MinValue;
    private string? _lastReported;

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        var interval = TimeSpan.FromSeconds(options.Value.HeartbeatIntervalSeconds);
        while (!stoppingToken.IsCancellationRequested)
        {
            try { await RunOnceAsync(DateTime.UtcNow, stoppingToken); }
            catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested) { break; }
            catch (Exception ex) { logger.LogError(ex, "Browser policy cycle failed"); }
            try { await Task.Delay(interval, stoppingToken); }
            catch (OperationCanceledException) { break; }
        }
    }

    internal async Task RunOnceAsync(DateTime nowUtc, CancellationToken ct)
    {
        if (subscription.Dormant)
            return;
        var token = await enrollment.GetDeviceTokenAsync(ct);
        if (token is null)
            return;
        if (token != _currentFor)
        {
            // Re-enrolled: a new device row on the server, with nothing reported yet.
            (_currentFor, _nextFetch, _lastReported) = (token, DateTime.MinValue, null);
        }

        if (nowUtc >= _nextFetch)
        {
            var fetched = await api.GetBrowserPolicyAsync(token, ct);
            if (fetched is not null)
            {
                _current = fetched;
                _nextFetch = nowUtc + FetchInterval;
            }
            else
            {
                _nextFetch = nowUtc + RetryAfterFailure;   // keep what we have, ask again soon
            }
        }
        if (_current is null)
            return;   // never heard from the backend: there is nothing to apply or remove

        var policy = _current.Policy.ToPolicy();
        if (policy.UsbMode == "on_request")
        {
            // C3: only a PC in this mode asks, every cycle, so a window IT opens reaches it within a
            // minute. Unreachable: keep the last known end, which the PC enforces by itself.
            if (await api.GetUsbWindowAsync(token, ct) is { } window)
                _usbWriteUntil = window.Until?.UtcDateTime;
            policy = policy with { UsbWriteUntil = _usbWriteUntil };
        }
        else
        {
            _usbWriteUntil = null;
        }

        var reports = Apply(policy);
        // C3b: the USB drives this PC has seen go with the report, while AI Guard is on, so an
        // admin can approve the company's own.
        var drives = _current.Version > 0 ? Drives() : [];
        var signature = $"{_current.Version}|" + string.Join("|", reports.Select(r =>
            $"{r.Browser}:{string.Join(",", r.Conflicts.Order())}:{r.Error}")) + "|" + string.Join(",", drives.Select(d => d.Id));
        var closed = _closed.ToDictionary();
        if (reports.Any(r => r.Changed) || signature != _lastReported || closed.Count > 0)
        {
            if (await api.ReportBrowserPolicyAsync(token, _current.Version, reports, closed, drives, ct))
            {
                _lastReported = signature;
                foreach (var (name, n) in closed)   // closes counted meanwhile stay for the next report
                    if (_closed.AddOrUpdate(name, 0, (_, now) => now - n) == 0)
                        _closed.TryRemove(new KeyValuePair<string, int>(name, 0));
            }
        }
        // A new version also rewrites values, so this cannot say who changed them; the backend,
        // which knows the last version this PC reported, decides what is tampering.
        foreach (var r in reports.Where(r => r.Repaired.Count > 0))
            logger.LogWarning("Browser policy for {Browser} differed from the org's and was rewritten: {Names}",
                              r.Browser, string.Join(", ", r.Repaired));

        await SyncApprovalsAsync(token, _current.Policy.ToPolicy(), ct);
    }

    /// <summary>D7: only a PC whose org asks for approvals fetches them, every cycle, so an
    /// approval reaches the person within a minute. Every other PC makes no extra call.</summary>
    async Task SyncApprovalsAsync(string token, BrowserPolicy policy, CancellationToken ct)
    {
        var wanted = policy.GuardMode == "approve" &&
                     (policy.ChromeExtensionId ?? policy.EdgeExtensionId ?? policy.FirefoxExtensionId) is not null;
        try
        {
            if (wanted)
            {
                if (await api.GetGuardApprovalsAsync(token, ct) is { } approvals)
                {
                    StoreApprovals(approvals);
                    _approvalsMayBeStored = true;
                }
            }
            else if (_approvalsMayBeStored)
            {
                StoreApprovals([]);
                _approvalsMayBeStored = false;
            }
        }
        catch (Exception ex) when (ex is UnauthorizedAccessException or System.Security.SecurityException or IOException)
        {
            logger.LogWarning(ex, "Could not store browser guard approvals");
        }
    }
}
