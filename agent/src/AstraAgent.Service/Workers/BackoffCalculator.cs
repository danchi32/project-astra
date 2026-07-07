namespace AstraAgent.Service.Workers;

public static class BackoffCalculator
{
    /// <summary>Exponential backoff: base interval on success, doubling per consecutive
    /// failure, capped at <paramref name="max"/>.</summary>
    public static TimeSpan NextDelay(int consecutiveFailures, TimeSpan baseInterval, TimeSpan max)
    {
        if (consecutiveFailures <= 0)
            return baseInterval;
        var multiplier = Math.Pow(2, Math.Min(consecutiveFailures, 10));
        var delayTicks = baseInterval.Ticks * (double)multiplier;
        return delayTicks >= max.Ticks ? max : TimeSpan.FromTicks((long)delayTicks);
    }
}
