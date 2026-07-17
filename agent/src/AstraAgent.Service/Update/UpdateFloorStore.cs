namespace AstraAgent.Service.Update;

/// <summary>Remembers the highest agent version this device has ever seen in a validly-signed
/// manifest. Combined with the running version and any signed <c>min_version</c>, this forms a
/// monotonic floor: once the agent has learned that (say) 0.4.0 exists, a compromised or
/// man-in-the-middle backend replaying an older-but-still-signed 0.3.0 manifest is refused.
///
/// This does not defend an agent that has never once reached an honest backend after the newer
/// release — that residual (pure offline rollback of a never-seen version) needs a time-based
/// freshness field and is noted as a follow-up. The floor closes the far more likely window.
///
/// The file lives in the admin-only update working area (see <see cref="UpdatePaths"/>), so an
/// unprivileged user can't lower it.</summary>
public sealed class UpdateFloorStore
{
    private readonly string _path;

    public UpdateFloorStore(string? path = null)
        => _path = path ?? Path.Combine(UpdatePaths.WorkRoot, "version-floor.txt");

    public string Current()
    {
        try
        {
            if (File.Exists(_path))
            {
                var v = File.ReadAllText(_path).Trim();
                if (!string.IsNullOrEmpty(v))
                    return v;
            }
        }
        catch { /* unreadable — treat as no floor */ }
        return "0.0.0";
    }

    /// <summary>Raise the floor to <paramref name="version"/> if it's higher than what's stored.
    /// Never lowers it. Best-effort persistence.</summary>
    public void Raise(string version)
    {
        try
        {
            if (SemVer.IsNewer(version, Current()))
                File.WriteAllText(_path, version);
        }
        catch { /* best effort — a missed raise only weakens replay defense, never breaks updates */ }
    }
}
