using System.Management;

namespace AstraAgent.Service.Telemetry.Collectors;

public sealed class HardwareCollector(
    IDiskCollector diskCollector,
    ILogger<HardwareCollector> logger) : IHardwareCollector
{
    public HardwareInfo GetHardwareInfo()
    {
        string? manufacturer = null;
        string? model = null;
        long? totalRamMb = null;
        string? cpuName = null;

        try
        {
            using var searcher = new ManagementObjectSearcher(
                "SELECT Manufacturer, Model, TotalPhysicalMemory FROM Win32_ComputerSystem");
            foreach (var obj in searcher.Get())
            {
                manufacturer = CleanString(obj["Manufacturer"]?.ToString());
                model = CleanString(obj["Model"]?.ToString());
                if (obj["TotalPhysicalMemory"] is not null &&
                    ulong.TryParse(obj["TotalPhysicalMemory"].ToString(), out var bytes))
                {
                    totalRamMb = (long)(bytes / 1024 / 1024);
                }
                break;
            }
        }
        catch (Exception ex)
        {
            logger.LogWarning(ex, "Could not read Win32_ComputerSystem");
        }

        try
        {
            using var searcher = new ManagementObjectSearcher("SELECT Name FROM Win32_Processor");
            foreach (var obj in searcher.Get())
            {
                cpuName = CleanString(obj["Name"]?.ToString());
                break;
            }
        }
        catch (Exception ex)
        {
            logger.LogWarning(ex, "Could not read Win32_Processor");
        }

        // Total fixed-disk capacity, summed from the disk collector.
        double? totalStorageGb = null;
        try
        {
            var disks = diskCollector.GetDiskInfo();
            if (disks.Count > 0)
                totalStorageGb = Math.Round(disks.Sum(d => d.TotalGb), 1);
        }
        catch (Exception ex)
        {
            logger.LogWarning(ex, "Could not sum disk capacity");
        }

        return new HardwareInfo(manufacturer, model, cpuName, totalRamMb, totalStorageGb);
    }

    private static string? CleanString(string? value)
    {
        if (string.IsNullOrWhiteSpace(value))
            return null;
        var trimmed = value.Trim();
        return trimmed.Length <= 200 ? trimmed : trimmed[..200];
    }
}
