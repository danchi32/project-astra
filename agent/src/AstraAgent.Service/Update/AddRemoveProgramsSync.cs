using System;
using System.IO;
using Microsoft.Win32;

namespace AstraAgent.Service.Update;

/// <summary>What, if anything, the Add/Remove Programs entry needs changed.</summary>
/// <param name="DisplayVersion">New DisplayVersion to write, or null to leave it.</param>
/// <param name="DisplayIcon">New DisplayIcon to write, or null to leave it.</param>
public sealed record ArpRepair(string? DisplayVersion, string? DisplayIcon)
{
    public bool IsEmpty => DisplayVersion is null && DisplayIcon is null;
}

/// <summary>Keeps Control Panel's "Programs and Features" entry honest after an auto-update.
///
/// The version of the agent is written in three places, and until now only two of them moved.
/// The assembly reports itself at runtime (that is what the portal shows), the update swaps the
/// binaries on disk — and the Add/Remove Programs entry is written ONLY by the Inno Setup
/// installer. So every auto-updated device kept showing the version of the installer that was
/// last RUN. A machine installed at 0.8.2 and updated over the air to 0.8.8 showed 0.8.2 in
/// Control Panel and 0.8.8 in the portal, and both were "right", which is the worst kind of
/// disagreement: nothing is broken, nobody can prove it, and the number an administrator
/// reaches for first is the stale one.
///
/// The same omission explains a blank icon. `UninstallDisplayIcon` arrived in 0.8.3, so entries
/// written by an earlier installer have no DisplayIcon at all and Windows draws the generic
/// page. An update could never fix it, because an update never touched the key.
///
/// This runs at service start rather than only after applying an update, which is deliberate:
/// it repairs devices that are ALREADY in the wrong state — the ones that took the update that
/// caused the drift — instead of only preventing the next one. It is idempotent and silent when
/// there is nothing to do.
///
/// What it will NOT do is create the key. A machine installed from the portable zip has no
/// Add/Remove Programs entry by design, and inventing one would put an entry in Control Panel
/// whose Uninstall button does nothing.</summary>
public static class AddRemoveProgramsSync
{
    // Inno Setup registers under the AppId with "_is1" appended — see AstraAgent.iss, where
    // AppId is written {{8F3C61D4-…} because the doubled brace is Inno's escape for a literal.
    internal const string UninstallSubKey =
        @"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{8F3C61D4-6B2A-4E57-9A18-2D7E4C0B93A5}_is1";

    /// <summary>Decides what to change, given what the key currently holds and which icon
    /// candidates exist on disk. Pure, so the judgement is testable without a registry: the
    /// interesting part is not writing values, it is knowing when NOT to.</summary>
    /// <param name="currentVersion">What this binary reports (AgentVersion.Current).</param>
    /// <param name="recordedVersion">The key's existing DisplayVersion.</param>
    /// <param name="recordedIcon">The key's existing DisplayIcon.</param>
    /// <param name="recordedIconExists">Whether that DisplayIcon actually resolves to a file.</param>
    /// <param name="iconCandidate">The best icon path that exists on this machine, or null.</param>
    public static ArpRepair Plan(
        string currentVersion,
        string? recordedVersion,
        string? recordedIcon,
        bool recordedIconExists,
        string? iconCandidate)
    {
        string? version = null;
        // Only when it actually differs. Writing the same value every start would churn the
        // registry and, more to the point, make the audit of what changed useless.
        if (!string.IsNullOrWhiteSpace(currentVersion)
            && currentVersion != "0.0.0"
            && !string.Equals(currentVersion, (recordedVersion ?? string.Empty).Trim(),
                              StringComparison.OrdinalIgnoreCase))
        {
            version = currentVersion;
        }

        string? icon = null;
        // Repair a missing icon, and a stale one that points at a file no longer there — the
        // second case is what an install that has moved or been partially cleaned looks like.
        // An icon that IS present and resolves is left alone even if we would have chosen
        // differently: it was the installer's decision and it works.
        var iconBroken = string.IsNullOrWhiteSpace(recordedIcon) || !recordedIconExists;
        if (iconBroken && !string.IsNullOrWhiteSpace(iconCandidate))
            icon = iconCandidate;

        return new ArpRepair(version, icon);
    }

    /// <summary>Applies the repair if the entry exists. Never throws: a service that cannot
    /// start because Control Panel would look slightly wrong is a far worse outcome than the
    /// cosmetic problem it is fixing.</summary>
    public static void Run(string installDir, string currentVersion, ILogger? logger = null)
    {
        try
        {
            // {app} is the parent of the service's own directory: the installer lays out
            // …\Astra\Agent and …\Astra\Tray beneath …\Astra.
            var appRoot = Path.GetDirectoryName(installDir.TrimEnd('\\')) ?? installDir;
            var candidate = PickIcon(appRoot);

            // Both views: the installer is 64-bit, but a machine that has been through an
            // architecture change can carry the entry in either.
            foreach (var view in new[] { RegistryView.Registry64, RegistryView.Registry32 })
            {
                using var baseKey = RegistryKey.OpenBaseKey(RegistryHive.LocalMachine, view);
                using var key = baseKey.OpenSubKey(UninstallSubKey, writable: true);
                if (key is null) continue;   // no installer-written entry — see the class note

                var recordedIcon = key.GetValue("DisplayIcon") as string;
                var repair = Plan(
                    currentVersion,
                    key.GetValue("DisplayVersion") as string,
                    recordedIcon,
                    IconResolves(recordedIcon),
                    candidate);

                if (repair.IsEmpty) return;

                if (repair.DisplayVersion is not null)
                    key.SetValue("DisplayVersion", repair.DisplayVersion, RegistryValueKind.String);
                if (repair.DisplayIcon is not null)
                    key.SetValue("DisplayIcon", repair.DisplayIcon, RegistryValueKind.String);

                logger?.LogInformation(
                    "Add/Remove Programs entry refreshed (version {Version}, icon {Icon})",
                    repair.DisplayVersion ?? "unchanged", repair.DisplayIcon ?? "unchanged");
                return;
            }
        }
        catch (Exception ex)
        {
            logger?.LogWarning(ex, "Could not refresh the Add/Remove Programs entry");
        }
    }

    /// <summary>The best icon on this machine, or null if neither is present.
    ///
    /// astra.ico first, because that is what the installer chose and it is a plain icon file
    /// that nothing else rewrites. The tray executable is the fallback and the one that matters
    /// here: it is a WinExe carrying the ASTRA mark as a native resource, and — unlike the .ico —
    /// it IS part of the update payload, so it exists even on a device installed before 0.8.3
    /// which never received the icon file at all. That is precisely the case this repairs.
    ///
    /// Not used: the service's own binary. It ships framework-dependent, so what lands on disk
    /// is AstraAgent.Service.dll — a library, with no icon resource for Windows to draw.</summary>
    internal static string? PickIcon(string appRoot)
    {
        var ico = Path.Combine(appRoot, "astra.ico");
        if (File.Exists(ico)) return ico;

        var tray = Path.Combine(appRoot, "Tray", "AstraAgent.Tray.exe");
        if (File.Exists(tray)) return tray;

        return null;
    }

    /// <summary>Whether a recorded DisplayIcon still points at something. The value may carry
    /// an ",index" suffix (Windows' icon-within-a-file syntax), which is not part of the path.</summary>
    private static bool IconResolves(string? recorded)
    {
        var value = (recorded ?? string.Empty).Trim().Trim('"');
        if (value.Length == 0) return false;

        var comma = value.LastIndexOf(',');
        if (comma > 2 && int.TryParse(value[(comma + 1)..], out _))
            value = value[..comma];

        return File.Exists(value.Trim().Trim('"'));
    }
}
