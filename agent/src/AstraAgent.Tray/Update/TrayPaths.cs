using System;
using System.IO;

namespace AstraAgent.Tray.Update;

/// <summary>Locations for the tray's self-updating "live" copy.
///
/// The installer seeds the tray into Program Files (read-only to a normal user). On startup the
/// tray hands off to a per-user, user-writable live copy under LocalAppData, from which it can
/// replace its own files without elevation. This makes the tray per-user automatically — each
/// Windows user who logs in gets their own live copy — with no installer changes.</summary>
internal static class TrayPaths
{
    /// <summary>`%LocalAppData%\Astra\Tray` — the user-writable live copy the tray runs from
    /// and self-updates in place.</summary>
    public static string LiveDir { get; } = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
        "Astra", "Tray");

    /// <summary>Records the version currently staged in <see cref="LiveDir"/>, so the seed can
    /// tell whether the live copy is already at least as new as itself.</summary>
    public static string VersionMarker => Path.Combine(LiveDir, "version.txt");

    /// <summary>Scratch area for downloads/staging, under the live dir (user-writable).</summary>
    public static string UpdateWorkDir => Path.Combine(LiveDir, ".update");

    public static string ReadLiveVersion()
    {
        try
        {
            if (File.Exists(VersionMarker))
            {
                var v = File.ReadAllText(VersionMarker).Trim();
                if (!string.IsNullOrEmpty(v))
                    return v;
            }
        }
        catch { /* unreadable — treat as absent */ }
        return "0.0.0";
    }

    public static bool RunningFromLiveDir()
    {
        var here = AppContext.BaseDirectory.TrimEnd('\\');
        return string.Equals(here, LiveDir.TrimEnd('\\'), StringComparison.OrdinalIgnoreCase);
    }
}
