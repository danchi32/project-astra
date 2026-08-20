using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.ServiceProcess;

namespace AstraAgent.Service.Remediation;

/// <summary>Resets Windows Update by clearing the two caches it corrupts — the standard fix
/// for updates that download forever or fail with the same error every time.
///
/// The caches are renamed, never deleted: Windows rebuilds both on the next check, and a
/// rename is reversible if this turns out not to have been the problem. That is also why the
/// old copies are left on disk rather than removed.
///
/// Everything here is destructive to in-flight updates, which is why the action is admin-only.
/// The services MUST be stopped first — Windows holds both folders open — so a failure to
/// stop is a hard stop, not something to push past.</summary>
public static class WindowsUpdateComponents
{
    // wuauserv downloads, BITS transfers, CryptSvc owns catroot2, msiserver installs.
    private static readonly string[] Services = { "wuauserv", "bits", "cryptsvc", "msiserver" };

    private static readonly TimeSpan StateTimeout = TimeSpan.FromSeconds(60);

    public static (bool Success, string Output) Reset()
    {
        var windows = Environment.GetFolderPath(Environment.SpecialFolder.Windows);
        var softwareDistribution = Path.Combine(windows, "SoftwareDistribution");
        var catroot2 = Path.Combine(windows, "System32", "catroot2");

        var stopped = new List<string>();
        try
        {
            foreach (var name in Services)
            {
                var controller = Stop(name);
                if (controller is not null) stopped.Add(name);
            }

            // Stopping is not optional. Renaming a folder Windows Update still holds open
            // fails halfway and leaves the machine in a worse state than before.
            var stillRunning = Services.Where(IsRunning).ToList();
            if (stillRunning.Count > 0)
            {
                Start(stopped);
                return (false,
                    $"Could not stop {string.Join(", ", stillRunning)}, so the update caches were "
                    + "left untouched. A restart of the PC will release them.");
            }

            var renamed = new List<string>();
            foreach (var folder in new[] { softwareDistribution, catroot2 })
            {
                var (ok, detail) = RenameAside(folder);
                if (!ok)
                {
                    Start(stopped);
                    return (false, $"Could not clear {Path.GetFileName(folder)}: {detail}");
                }
                if (detail.Length > 0) renamed.Add(detail);
            }

            Start(stopped);

            if (renamed.Count == 0)
                return (true,
                    "Windows Update's caches were already absent — nothing needed clearing, and "
                    + "the update services were restarted.");

            return (true,
                $"Reset Windows Update: {string.Join(" and ", renamed)}. Windows rebuilds both on "
                + "the next update check, and the renamed copies are left on disk in case they "
                + "are needed. The first check after this will take longer than usual.");
        }
        catch (Exception ex)
        {
            Start(stopped);
            return (false, "Could not reset Windows Update components: " + ex.Message);
        }
    }

    /// <summary>Renames a folder out of the way. Reports "" when there was nothing there.</summary>
    private static (bool Ok, string Detail) RenameAside(string folder)
    {
        if (!Directory.Exists(folder)) return (true, "");

        var aside = folder + ".old";
        try
        {
            // A previous run's copy would block the rename; only the most recent is kept.
            if (Directory.Exists(aside)) Directory.Delete(aside, recursive: true);
            Directory.Move(folder, aside);
            return (true, $"renamed {Path.GetFileName(folder)} to {Path.GetFileName(aside)}");
        }
        catch (Exception ex)
        {
            return (false, ex.Message);
        }
    }

    private static bool IsRunning(string name)
    {
        try
        {
            using var controller = new ServiceController(name);
            return controller.Status != ServiceControllerStatus.Stopped;
        }
        catch
        {
            return false;   // not installed on this edition — nothing to stop
        }
    }

    private static ServiceController? Stop(string name)
    {
        try
        {
            var controller = new ServiceController(name);
            if (controller.Status == ServiceControllerStatus.Stopped) return controller;
            controller.Stop();
            controller.WaitForStatus(ServiceControllerStatus.Stopped, StateTimeout);
            return controller;
        }
        catch
        {
            return null;
        }
    }

    /// <summary>Best effort, and deliberately so: this runs on the failure paths too, where
    /// leaving Windows Update stopped would be worse than the problem being fixed.</summary>
    private static void Start(IEnumerable<string> names)
    {
        foreach (var name in names)
        {
            try
            {
                using var controller = new ServiceController(name);
                if (controller.Status == ServiceControllerStatus.Running) continue;
                controller.Start();
                controller.WaitForStatus(ServiceControllerStatus.Running, StateTimeout);
            }
            catch { /* reported by the caller's own message; never mask the original failure */ }
        }
    }
}
