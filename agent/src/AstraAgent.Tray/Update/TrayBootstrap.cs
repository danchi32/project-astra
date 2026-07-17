using System;
using System.Diagnostics;
using System.IO;
using AstraAgent.Service;
using AstraAgent.Service.Update;

namespace AstraAgent.Tray.Update;

/// <summary>Hands the running tray off to its user-writable live copy so it can self-update.
///
/// Flow: the Run key launches the Program Files seed → the seed ensures LocalAppData holds a
/// copy at least as new as itself, then launches that copy and exits. Thereafter the tray runs
/// from LocalAppData and updates itself in place. Any failure falls back to running the seed in
/// place (the tray still works; it just won't self-update) — never a crash, never no tray.</summary>
public static class TrayBootstrap
{
    /// <summary>Returns true if this process handed off to the live copy and should now exit.</summary>
    public static bool HandoffIfNeeded()
    {
        try
        {
            if (TrayPaths.RunningFromLiveDir())
                return false;   // already the live copy — run here and self-update

            var seedDir = AppContext.BaseDirectory.TrimEnd('\\');
            var seedVersion = AgentVersion.Current;
            var liveDll = Path.Combine(TrayPaths.LiveDir, "AstraAgent.Tray.dll");

            // Seed the live copy the first time, or refresh it when a freshly-installed seed is
            // newer than whatever self-updated copy is there (e.g. after a manual reinstall).
            if (NeedsReseed(seedVersion, TrayPaths.ReadLiveVersion(), File.Exists(liveDll)))
            {
                CopyDir(seedDir, TrayPaths.LiveDir);
                File.WriteAllText(TrayPaths.VersionMarker, seedVersion);
            }

            if (!File.Exists(liveDll))
                return false;   // seeding failed — run in place instead

            LaunchLive(liveDll);
            return true;
        }
        catch (Exception)
        {
            return false;   // any trouble — fall back to running the seed in place
        }
    }

    /// <summary>Re-seed the live copy when there isn't one yet, or when a freshly installed seed
    /// is strictly newer than the self-updated live copy. Never re-seeds over an equal-or-newer
    /// live copy (that would clobber a self-update with an older bundled build).</summary>
    public static bool NeedsReseed(string seedVersion, string liveVersion, bool liveDllExists)
        => !liveDllExists || SemVer.IsNewer(seedVersion, liveVersion);

    private static void LaunchLive(string liveDll)
    {
        // Relaunch through the same dotnet host that is running us (ProcessPath is dotnet.exe).
        var host = Environment.ProcessPath ?? "dotnet";
        Process.Start(new ProcessStartInfo
        {
            FileName = host,
            Arguments = $"\"{liveDll}\"",
            WorkingDirectory = TrayPaths.LiveDir,
            UseShellExecute = false,
        });
    }

    private static void CopyDir(string source, string dest)
    {
        Directory.CreateDirectory(dest);
        foreach (var dir in Directory.GetDirectories(source, "*", SearchOption.AllDirectories))
            Directory.CreateDirectory(dir.Replace(source, dest));
        foreach (var file in Directory.GetFiles(source, "*", SearchOption.AllDirectories))
        {
            // Don't recurse into our own update scratch area if seed == a prior live dir.
            if (file.Contains(Path.Combine(".update", ""), StringComparison.OrdinalIgnoreCase))
                continue;
            File.Copy(file, file.Replace(source, dest), overwrite: true);
        }
    }
}
