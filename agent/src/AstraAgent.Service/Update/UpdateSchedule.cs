namespace AstraAgent.Service.Update;

/// <summary>When an updater checks the channel — with randomness folded in so a fleet that booted
/// together doesn't poll, and then download, in the same minute.
///
/// Both updaters (the service and the tray) used fixed delays, so every agent on a site that was
/// imaged or rebooted together lined up on the same tick: fifty machines hitting the update
/// channel at once and, worse, fifty full-package downloads starting at once over one site uplink.
/// Spreading the first check and jittering every interval after it breaks that herd. It does NOT
/// reduce the bytes a site pulls — that is the background-transfer side (see BitsDownloader) — it
/// only stops them all arriving at the same instant. Pure arithmetic, shared so neither updater
/// grows its own copy.</summary>
public static class UpdateSchedule
{
    /// <summary>The first check: <paramref name="baseDelay"/> (let enrollment settle) plus a random
    /// spread of up to <paramref name="spreadSeconds"/>, so first checks fan out across the fleet.</summary>
    public static TimeSpan FirstCheckDelay(TimeSpan baseDelay, int spreadSeconds, Random rnd)
        => baseDelay + TimeSpan.FromSeconds(rnd.Next(0, Math.Max(1, spreadSeconds)));

    /// <summary>A steady-state interval with up to 20% extra random delay, so checks that happened
    /// to align once don't stay aligned forever.</summary>
    public static TimeSpan JitteredInterval(TimeSpan interval, Random rnd)
    {
        var extra = (int)(interval.TotalSeconds * 0.2);
        return interval + TimeSpan.FromSeconds(rnd.Next(0, Math.Max(1, extra)));
    }
}
