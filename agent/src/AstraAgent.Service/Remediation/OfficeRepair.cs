using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using Microsoft.Win32;

namespace AstraAgent.Service.Remediation;

/// <summary>Runs Office's own repair — the fix for "Outlook/Word keeps crashing".
///
/// This drives OfficeClickToRun.exe, the same engine the Repair button in Settings uses, so
/// nothing here reimplements Microsoft's repair. Two facts shape the code:
///
///   * Only Click-to-Run installs (Microsoft 365, Office 2016 and later) can be repaired this
///     way. Older MSI installs need msiexec with a product code, and getting that wrong
///     repairs — or removes — the wrong product, so those are refused with an explanation
///     instead of guessed at.
///   * The repair force-closes every Office app. Running as LocalSystem there is no desktop
///     to warn on, so the caller must say so: this action is approval-gated precisely because
///     someone has to accept losing unsaved work.</summary>
public static class OfficeRepair
{
    private const string ConfigKey = @"SOFTWARE\Microsoft\Office\ClickToRun\Configuration";

    /// <summary>A quick repair is offline and takes a couple of minutes; a full repair
    /// re-downloads Office and can take far longer. Quick fixes the crash-on-launch cases,
    /// so it is what runs — but the timeout is generous because a slow disk is not a
    /// failure.</summary>
    private static readonly TimeSpan RepairTimeout = TimeSpan.FromMinutes(30);

    public sealed record Plan(string FileName, IReadOnlyList<string> Arguments);

    /// <summary>Builds the repair command, or explains why this PC cannot be repaired here.
    ///
    /// Pure, given what was found on disk and in the registry, so the argument construction —
    /// the part that decides what Office actually does — is testable without an Office
    /// install. Callers pass what they discovered; see <see cref="Repair"/>.</summary>
    public static (Plan? Plan, string? Refusal) PlanFor(
        string? clickToRunPath, string? platform, string? culture)
    {
        if (string.IsNullOrWhiteSpace(clickToRunPath))
            return (null,
                "This PC does not have a Click-to-Run installation of Office, so there is "
                + "nothing for the built-in repair to act on. If Office was installed from an "
                + "MSI or a volume-licence package, repair it from Settings > Apps > "
                + "Microsoft Office > Modify.");

        // Both are recorded by the Office installer. Defaults match what a repair would pick
        // anyway; passing them explicitly keeps OfficeClickToRun from prompting.
        var plat = string.IsNullOrWhiteSpace(platform) ? "x64" : platform!.Trim();
        var cult = string.IsNullOrWhiteSpace(culture) ? "en-us" : culture!.Trim();

        return (new Plan(clickToRunPath!, new[]
        {
            "scenario=Repair",
            $"platform={plat}",
            $"culture={cult}",
            "RepairType=QuickRepair",
            // No UI: session 0 has no desktop, and a repair waiting on an invisible dialog
            // would hang until the timeout with nothing to show for it.
            "DisplayLevel=False",
        }), null);
    }

    /// <summary>Where Office records its Click-to-Run install. Null when it is not one.</summary>
    public static string? FindClickToRun()
    {
        foreach (var root in new[]
                 {
                     Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86),
                     Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles),
                 })
        {
            if (string.IsNullOrEmpty(root)) continue;
            var path = Path.Combine(root, "Common Files", "Microsoft Shared", "ClickToRun",
                                    "OfficeClickToRun.exe");
            if (File.Exists(path)) return path;
        }
        return null;
    }

    private static (string? Platform, string? Culture) ReadConfiguration()
    {
        try
        {
            using var key = RegistryKey
                .OpenBaseKey(RegistryHive.LocalMachine, RegistryView.Registry64)
                .OpenSubKey(ConfigKey);
            if (key is null) return (null, null);
            return (key.GetValue("Platform") as string, key.GetValue("ClientCulture") as string);
        }
        catch
        {
            return (null, null);   // fall back to the defaults in PlanFor
        }
    }

    /// <summary>What Office says it last did, and how that went.
    ///
    /// Click-to-Run records the outcome of each maintenance run here. That record is the only
    /// honest evidence a repair happened: OfficeClickToRun.exe is a launcher that hands the
    /// work to the Click-to-Run service and exits 0 immediately, so its exit code says the
    /// request was accepted, not that anything was repaired.</summary>
    public static (string? Scenario, string? Result) ReadLastScenario()
    {
        try
        {
            using var key = RegistryKey
                .OpenBaseKey(RegistryHive.LocalMachine, RegistryView.Registry64)
                .OpenSubKey(ConfigKey);
            if (key is null) return (null, null);
            return (key.GetValue("LastScenario") as string,
                    key.GetValue("LastScenarioResult") as string);
        }
        catch
        {
            return (null, null);
        }
    }

    /// <summary>Turns what Office recorded into a verdict.
    ///
    /// Pure, and separate from running the repair, because deciding this from the launcher's
    /// exit code is exactly how a user was told "components were re-registered and damaged
    /// files replaced" while nothing whatsoever had happened on their PC.
    ///
    /// Not being able to confirm is reported as FAILURE, not success. A repair that cannot be
    /// evidenced is indistinguishable from one that never ran, and claiming the good case is
    /// what caused the original complaint.</summary>
    public static (bool Success, string Message) Verdict(string? scenario, string? result)
    {
        var didRepair = string.Equals(scenario, "REPAIR", StringComparison.OrdinalIgnoreCase);
        var succeeded = string.Equals(result, "Success", StringComparison.OrdinalIgnoreCase);

        if (didRepair && succeeded)
            return (true,
                "Office's quick repair completed — Windows recorded it as successful. Any Office "
                + "apps that were open were closed by the repair and can be reopened now. If the "
                + "crashes continue, a full (online) repair is the next step.");

        if (didRepair && !string.IsNullOrWhiteSpace(result))
            return (false,
                $"Office ran the repair but recorded the result as '{result}'. Office was not "
                + "repaired. Running Repair from Settings > Apps > Microsoft Office > Modify "
                + "will show the reason.");

        // Nothing recorded, or Office recorded some other activity: the repair never took.
        // The usual cause is Click-to-Run declining to run a silent repair in this context.
        return (false,
            "The repair did not run — Office recorded no repair having taken place"
            + (string.IsNullOrWhiteSpace(scenario) ? "" : $" (its last action was '{scenario}')")
            + ". Repair it from Settings > Apps > Microsoft Office > Modify on the device.");
    }

    public static (bool Success, string Output) Repair()
    {
        var exe = FindClickToRun();
        var (platform, culture) = ReadConfiguration();
        var (plan, refusal) = PlanFor(exe, platform, culture);
        if (plan is null) return (false, refusal!);

        try
        {
            var psi = new ProcessStartInfo
            {
                FileName = plan.FileName,
                UseShellExecute = false,
                CreateNoWindow = true,
            };
            foreach (var arg in plan.Arguments) psi.ArgumentList.Add(arg);

            // What Office had last recorded, so a stale "Repair/Success" from weeks ago cannot
            // be mistaken for this run's outcome.
            var before = ReadLastScenario();

            using var process = Process.Start(psi);
            if (process is null) return (false, "Could not start Office's repair tool.");

            // This exits within seconds regardless: it hands the work to the Click-to-Run
            // service. Waiting on it proves only that the request was accepted.
            process.WaitForExit(120_000);
            if (process.ExitCode != 0)
                return (false,
                    $"Office's repair tool would not start (exit code {process.ExitCode}). "
                    + "Repair it from Settings > Apps > Microsoft Office > Modify on the device.");

            // The actual repair runs behind that. Watch Office's own record until it changes,
            // which is the only thing that distinguishes a repair from a launcher exiting 0.
            var deadline = DateTime.UtcNow + RepairTimeout;
            var after = before;
            while (DateTime.UtcNow < deadline)
            {
                System.Threading.Thread.Sleep(10_000);
                after = ReadLastScenario();
                var settled = !string.IsNullOrWhiteSpace(after.Result)
                              && string.Equals(after.Scenario, "REPAIR", StringComparison.OrdinalIgnoreCase);
                if (settled && after != before)
                    break;
            }

            if (after == before)
                return (false,
                    $"Office reported nothing after {RepairTimeout.TotalMinutes:0} minutes — its "
                    + "record of the last maintenance run is unchanged, so the repair did not "
                    + "take. Repair it from Settings > Apps > Microsoft Office > Modify.");

            return Verdict(after.Scenario, after.Result);
        }
        catch (Exception ex)
        {
            return (false, "Could not run Office repair: " + ex.Message);
        }
    }
}
