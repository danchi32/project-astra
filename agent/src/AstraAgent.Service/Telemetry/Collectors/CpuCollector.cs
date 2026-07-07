using System.Diagnostics;

namespace AstraAgent.Service.Telemetry.Collectors;

public sealed class CpuCollector(ILogger<CpuCollector> logger) : ICpuCollector
{
    public async Task<float> GetCpuPercentAsync(CancellationToken ct)
    {
        try
        {
            using var counter = new PerformanceCounter("Processor", "% Processor Time", "_Total");
            // First read always returns 0 — discard it, wait briefly, then read the real value.
            counter.NextValue();
            await Task.Delay(500, ct);
            return MathF.Round(counter.NextValue(), 1);
        }
        catch (Exception ex)
        {
            logger.LogWarning(ex, "CPU collection failed");
            return 0f;
        }
    }
}
