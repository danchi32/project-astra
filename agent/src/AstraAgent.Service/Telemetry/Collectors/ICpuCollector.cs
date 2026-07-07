namespace AstraAgent.Service.Telemetry.Collectors;

public interface ICpuCollector
{
    /// <summary>Returns current CPU utilisation as a percentage (0–100).</summary>
    Task<float> GetCpuPercentAsync(CancellationToken ct);
}
