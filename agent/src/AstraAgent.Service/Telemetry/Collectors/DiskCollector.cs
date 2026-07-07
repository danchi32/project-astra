namespace AstraAgent.Service.Telemetry.Collectors;

public sealed class DiskCollector(ILogger<DiskCollector> logger) : IDiskCollector
{
    public IReadOnlyList<DiskInfo> GetDiskInfo()
    {
        var result = new List<DiskInfo>();
        try
        {
            foreach (var drive in DriveInfo.GetDrives())
            {
                if (drive.DriveType != DriveType.Fixed || !drive.IsReady)
                    continue;
                var totalGb = Math.Round(drive.TotalSize / 1_073_741_824.0, 1);
                var freeGb = Math.Round(drive.TotalFreeSpace / 1_073_741_824.0, 1);
                result.Add(new DiskInfo(drive.Name, totalGb, Math.Round(totalGb - freeGb, 1), freeGb));
            }
        }
        catch (Exception ex)
        {
            logger.LogWarning(ex, "Disk collection failed");
        }
        return result;
    }
}
