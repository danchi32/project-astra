namespace AstraAgent.Service.Telemetry.Collectors;

public sealed record DiskInfo(string Drive, double TotalGb, double UsedGb, double FreeGb);

public interface IDiskCollector
{
    IReadOnlyList<DiskInfo> GetDiskInfo();
}
