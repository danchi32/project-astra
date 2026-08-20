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

            using var process = Process.Start(psi);
            if (process is null) return (false, "Could not start Office's repair tool.");

            if (!process.WaitForExit((int)RepairTimeout.TotalMilliseconds))
            {
                // Leave it running rather than killing a half-finished repair, which is how an
                // Office install ends up in a worse state than it started.
                return (false,
                    $"Office repair was still running after {RepairTimeout.TotalMinutes:0} minutes. "
                    + "It has been left to finish on its own — check Office again shortly.");
            }

            if (process.ExitCode != 0)
                return (false,
                    $"Office's repair tool exited with code {process.ExitCode}. Office was not "
                    + "repaired; running Repair from Settings > Apps will show the reason.");

            return (true,
                "Ran Office's quick repair — its components were re-registered and damaged files "
                + "replaced. Any Office apps that were open were closed by the repair and can be "
                + "reopened now. If the crashes continue, a full (online) repair is the next step.");
        }
        catch (Exception ex)
        {
            return (false, "Could not run Office repair: " + ex.Message);
        }
    }
}
