using AstraAgent.Service.Api;
using AstraAgent.Service.Enrollment;
using AstraAgent.Service.Telemetry.Collectors;
using AstraAgent.Service.Workforce;
using Microsoft.Extensions.Options;

namespace AstraAgent.Service.Workers;

/// <summary>Collects and ships a telemetry batch every heartbeat cycle.
/// Inventory (apps, services, updates) is collected once per hour to reduce overhead.</summary>
public sealed class TelemetryWorker(
    IEnrollmentService enrollment,
    IAstraApiClient api,
    ICpuCollector cpu,
    IMemoryCollector memory,
    IDiskCollector disk,
    IEventLogCollector events,
    IInstalledAppsCollector apps,
    IServicesCollector services,
    IWindowsUpdateCollector updates,
    IHardwareCollector hardware,
    ISessionCollector sessions,
    IActivityTracker activityTracker,
    ActivityTrackingState trackingState,
    SubscriptionState subscription,
    IOptions<AgentOptions> options,
    ILogger<TelemetryWorker> logger) : BackgroundService
{
    private static readonly TimeSpan InventoryInterval = TimeSpan.FromHours(1);
    // Same ceiling as the heartbeat. A device the backend refuses (its org's subscription has
    // ended) must not keep pushing every minute, which is a database lookup per push.
    private static readonly TimeSpan MaxBackoff = TimeSpan.FromMinutes(15);
    private DateTime _lastInventoryAt = DateTime.MinValue;

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        var interval = TimeSpan.FromSeconds(options.Value.HeartbeatIntervalSeconds);
        var failures = 0;

        while (!stoppingToken.IsCancellationRequested)
        {
            try
            {
                failures = await CollectAndPushAsync(stoppingToken) ? 0 : failures + 1;
            }
            catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested)
            {
                break;
            }
            catch (Exception ex)
            {
                failures++;
                logger.LogError(ex, "Telemetry cycle failed");
            }

            // A failed push doubles the wait, up to MaxBackoff. The heartbeat already does this.
            try { await Task.Delay(BackoffCalculator.NextDelay(failures, interval, MaxBackoff), stoppingToken); }
            catch (OperationCanceledException) { break; }
        }
    }

    /// <returns>True when there was nothing to send or the push was accepted; false when the
    /// backend refused or was unreachable, so the caller backs off.</returns>
    private async Task<bool> CollectAndPushAsync(CancellationToken ct)
    {
        // Dormant (organization inactive): collect nothing and send nothing. This is a local
        // check each cycle, so pushes resume within one interval of the heartbeat waking up.
        if (subscription.Dormant)
            return true;

        var token = await enrollment.GetDeviceTokenAsync(ct);
        if (token is null) return true;

        var now = DateTimeOffset.UtcNow;
        var collectInventory = now.UtcDateTime - _lastInventoryAt >= InventoryInterval;

        var cpuPct = await cpu.GetCpuPercentAsync(ct);
        var mem = memory.GetMemoryInfo();
        var diskList = disk.GetDiskInfo();
        var eventList = events.GetRecentEntries();
        var sessionList = sessions.GetSessions();

        // Workforce Insights ("Tracker"). Only when the backend has told us this org is
        // entitled (via the heartbeat) — null otherwise, so nothing is collected or sent, and
        // we don't even diff. Derived from the session list already in hand, so it costs a
        // dictionary comparison, not another sweep of the machine.
        var activityList = trackingState.Enabled
            ? activityTracker.Diff(sessionList, now)
                .Select(a => new TelemetryActivityEvent(a.Username, a.Kind, a.OccurredAt, a.SessionId))
                .ToList()
            : null;

        var payload = new TelemetryPush(
            CollectedAt: now,
            CpuPercent: cpuPct,
            RamTotalMb: mem.TotalMb,
            RamUsedMb: mem.UsedMb,
            Disks: diskList.Select(d => new TelemetryDiskInfo(d.Drive, d.TotalGb, d.UsedGb, d.FreeGb)).ToList(),
            Hardware: collectInventory ? ToHardware(hardware.GetHardwareInfo()) : null,
            EventLogs: eventList.Select(e => new TelemetryEventLogEntry(e.LogName, e.Source, e.EventId, e.Level, e.Message, e.OccurredAt)).ToList(),
            InstalledApps: collectInventory
                ? apps.GetInstalledApps().Select(a => new TelemetryInstalledApp(a.Name, a.Version, a.Publisher, a.InstallDate)).ToList()
                : [],
            Services: collectInventory
                ? services.GetServices().Select(s => new TelemetryServiceEntry(s.Name, s.DisplayName, s.Status, s.StartType)).ToList()
                : [],
            WindowsUpdates: collectInventory
                ? updates.GetUpdates().Select(u => new TelemetryWindowsUpdate(
                    u.KbArticleId, u.Title, u.IsInstalled, u.InstalledOn, u.State, u.ErrorCode)).ToList()
                : [],
            // Every cycle, not with the hourly inventory. Who is signed in changes on a scale
            // of minutes, and an hourly session list would show people at desks they left
            // fifty minutes ago — which is worse than no list, because it looks current.
            // The cost is a handful of rows: the backend fingerprints them and writes nothing
            // when nobody has signed in or out since the last push.
            Sessions: sessionList.Select(x => new TelemetrySessionEntry(
                x.SessionId, x.Username, x.State, x.Connection,
                x.Station, x.ClientName, x.LogonAt, x.IdleSeconds)).ToList(),
            Activity: activityList);

        var pushed = await api.PushTelemetryAsync(token, payload, ct);
        if (pushed && collectInventory)
            _lastInventoryAt = now.UtcDateTime;

        logger.LogInformation(
            "Telemetry pushed — CPU {Cpu:F1}% RAM {Ram}/{Total}MB Disks:{Disks} Sessions:{Sessions}",
            cpuPct, mem.UsedMb, mem.TotalMb, diskList.Count, sessionList.Count);
        return pushed;
    }

    private static TelemetryHardware ToHardware(HardwareInfo h) =>
        new(h.Manufacturer, h.Model, h.CpuName, h.TotalRamMb, h.TotalStorageGb);
}
