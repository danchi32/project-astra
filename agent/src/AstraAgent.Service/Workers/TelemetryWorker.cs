using AstraAgent.Service.Api;
using AstraAgent.Service.Enrollment;
using AstraAgent.Service.Telemetry.Collectors;
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
    IOptions<AgentOptions> options,
    ILogger<TelemetryWorker> logger) : BackgroundService
{
    private static readonly TimeSpan InventoryInterval = TimeSpan.FromHours(1);
    private DateTime _lastInventoryAt = DateTime.MinValue;

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        var interval = TimeSpan.FromSeconds(options.Value.HeartbeatIntervalSeconds);

        while (!stoppingToken.IsCancellationRequested)
        {
            try
            {
                await CollectAndPushAsync(stoppingToken);
            }
            catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested)
            {
                break;
            }
            catch (Exception ex)
            {
                logger.LogError(ex, "Telemetry cycle failed");
            }

            try { await Task.Delay(interval, stoppingToken); }
            catch (OperationCanceledException) { break; }
        }
    }

    private async Task CollectAndPushAsync(CancellationToken ct)
    {
        var token = await enrollment.GetDeviceTokenAsync(ct);
        if (token is null) return;

        var now = DateTimeOffset.UtcNow;
        var collectInventory = now.UtcDateTime - _lastInventoryAt >= InventoryInterval;

        var cpuPct = await cpu.GetCpuPercentAsync(ct);
        var mem = memory.GetMemoryInfo();
        var diskList = disk.GetDiskInfo();
        var eventList = events.GetRecentEntries();

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
                ? updates.GetUpdates().Select(u => new TelemetryWindowsUpdate(u.KbArticleId, u.Title, u.IsInstalled, u.InstalledOn)).ToList()
                : []);

        if (await api.PushTelemetryAsync(token, payload, ct) && collectInventory)
            _lastInventoryAt = now.UtcDateTime;

        logger.LogInformation(
            "Telemetry pushed — CPU {Cpu:F1}% RAM {Ram}/{Total}MB Disks:{Disks}",
            cpuPct, mem.UsedMb, mem.TotalMb, diskList.Count);
    }

    private static TelemetryHardware ToHardware(HardwareInfo h) =>
        new(h.Manufacturer, h.Model, h.CpuName, h.TotalRamMb, h.TotalStorageGb);
}
