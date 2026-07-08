namespace AstraAgent.Service.Telemetry.Collectors;

public sealed record HardwareInfo(
    string? Manufacturer,
    string? Model,
    string? CpuName,
    long? TotalRamMb,
    double? TotalStorageGb);

public interface IHardwareCollector
{
    HardwareInfo GetHardwareInfo();
}
