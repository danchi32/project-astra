namespace AstraAgent.Service.Telemetry.Collectors;

public sealed record HardwareInfo(
    string? Manufacturer,
    string? Model,
    string? CpuName,
    long? TotalRamMb,
    double? TotalStorageGb,
    // BIOS facts, sent hourly so a serial read wrong at enrollment (or never) gets corrected.
    // The serial goes as Windows reports it; the backend decides whether it is an OEM
    // placeholder ("To Be Filled By O.E.M.") rather than a real one.
    string? SerialNumber = null,
    string? BiosVersion = null,
    string? BiosReleaseDate = null);

public interface IHardwareCollector
{
    HardwareInfo GetHardwareInfo();
}
