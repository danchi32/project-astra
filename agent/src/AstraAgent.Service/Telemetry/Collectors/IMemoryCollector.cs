namespace AstraAgent.Service.Telemetry.Collectors;

public sealed record MemoryInfo(long TotalMb, long UsedMb);

public interface IMemoryCollector
{
    MemoryInfo GetMemoryInfo();
}
