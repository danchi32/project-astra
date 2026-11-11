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

        string? serial = null, biosVersion = null, biosDate = null;
        try
        {
            using var searcher = new ManagementObjectSearcher(
                "SELECT SerialNumber, SMBIOSBIOSVersion, ReleaseDate FROM Win32_BIOS");
            foreach (var obj in searcher.Get())
            {
                serial = CleanString(obj["SerialNumber"]?.ToString());
                biosVersion = CleanString(obj["SMBIOSBIOSVersion"]?.ToString());
                biosDate = ToIsoDate(obj["ReleaseDate"]?.ToString());
                break;
            }
        }
        catch (Exception ex)
        {
            logger.LogWarning(ex, "Could not read Win32_BIOS");
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

        return new HardwareInfo(manufacturer, model, cpuName, totalRamMb, totalStorageGb,
            serial, biosVersion, biosDate);
    }

    /// <summary>WMI's CIM datetime ("20230515000000.000000+000") as yyyy-MM-dd; null if it isn't one.</summary>
    internal static string? ToIsoDate(string? cimDate)
    {
        if (string.IsNullOrWhiteSpace(cimDate) || cimDate.Length < 8)
            return null;
        return DateTime.TryParseExact(cimDate[..8], "yyyyMMdd", null,
            System.Globalization.DateTimeStyles.None, out var d)
            ? d.ToString("yyyy-MM-dd")
            : null;
    }

    private static string? CleanString(string? value)
    {
        if (string.IsNullOrWhiteSpace(value))
            return null;
        var trimmed = value.Trim();
        return trimmed.Length <= 200 ? trimmed : trimmed[..200];
    }
}
