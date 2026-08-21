namespace AstraAgent.Service.Update;

/// <summary>The one decision both updaters make: may this offered release be installed?
///
/// The service and the tray update independently, and each used to carry its own copy of this
/// arithmetic. They drifted — a fix landed in one and not the other, and the tray's copy raised
/// the floor to the offered version *before* comparing against it, which made the comparison
/// unsatisfiable and quietly disabled tray self-update entirely. One shared implementation is the
/// point of this type; neither updater should grow a private version of it again.</summary>
public static class UpdatePolicy
{
    /// <summary>May <paramref name="manifestVersion"/> be applied, given the version we're running
    /// and the persisted anti-replay floor? The offer must be strictly newer than both.
    ///
    /// <paramref name="floorNow"/> must NOT already include the offered version. The floor records
    /// versions actually RUN; writing a merely-offered version into it makes the floor equal to
    /// the offer, strictly-newer can never hold, and the update is refused forever — a device
    /// stranded until some higher version ships.</summary>
    public static bool IsApplicable(string currentVersion, string manifestVersion, string floorNow)
    {
        var floor = floorNow;
        if (SemVer.Compare(currentVersion, floor) > 0)
            floor = currentVersion;
        return SemVer.IsNewer(manifestVersion, floor);
    }

    /// <summary>May a signed <c>min_version</c> be persisted into the floor? Only when it sits
    /// strictly below the offer. A mandatory release naming itself (min_version == version) would
    /// otherwise floor the agent at the very build it is being told to install; installing it
    /// raises the floor to that version on the next start anyway.</summary>
    public static bool ShouldPersistMinVersion(string manifestVersion, string? minVersion)
        => !string.IsNullOrEmpty(minVersion) && SemVer.IsNewer(manifestVersion, minVersion!);
}
