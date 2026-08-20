using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Diagnostics;
using Microsoft.Win32;

namespace AstraAgent.Tray.Remediation;

/// <summary>Opens Office's own repair, the way Control Panel does.
///
/// This lives in the TRAY, not the elevated service, and it does not compose the command —
/// both of those are the result of getting it wrong first.
///
/// The service ran OfficeClickToRun.exe as LocalSystem with
/// `scenario=Repair ... RepairType=QuickRepair DisplayLevel=False` and nothing happened, on
/// any invocation: not from the service, not from an elevated interactive shell, not from a
/// right-click Run as administrator. Two things were wrong.
///
///   * The command. Control Panel's Change button runs exactly what Windows recorded in the
///     product's ModifyPath — for Microsoft 365 that is `scenario=repair platform=x64
///     culture=en-us`, and nothing else. The two extra arguments were invented, and
///     DisplayLevel=False in particular appears to make Click-to-Run decline silently. So
///     the command is READ from the registry now, never built here: whatever Windows would
///     run for this machine's Office is what runs, across versions and editions.
///
///   * The context. Session 0 has no desktop, and this repair puts one up. LocalSystem is
///     already elevated, so elevation was never the missing piece — an interactive session
///     was. Running it from the tray with the runas verb gives both: the user's own session,
///     plus a UAC prompt their IT can authorise.
///
/// It therefore opens the repair rather than completing it: the person clicks Quick Repair
/// and follows it through, exactly as they would from Control Panel. Reporting anything
/// stronger than "it is open" would be another claim we cannot evidence.</summary>
public static class OfficeRepairLauncher
{
    private const string UninstallKey = @"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall";

    /// <summary>Splits a ModifyPath into the executable and its arguments.
    ///
    /// Pure, so the parsing can be tested against the real strings Windows stores. The path
    /// is quoted and the arguments are bare, e.g.
    ///   "C:\...\OfficeClickToRun.exe" scenario=repair platform=x64 culture=en-us
    /// Returns (null, ...) for anything that is not a quoted executable followed by
    /// arguments — an MSI product code, say, which several Office add-ins register here and
    /// which would uninstall a component rather than repair Office.</summary>
    public static (string? Executable, IReadOnlyList<string> Arguments) ParseModifyPath(string? modifyPath)
    {
        var raw = (modifyPath ?? string.Empty).Trim();
        if (!raw.StartsWith("\"", StringComparison.Ordinal))
            return (null, Array.Empty<string>());

        var closing = raw.IndexOf('"', 1);
        if (closing <= 1)
            return (null, Array.Empty<string>());

        var exe = raw.Substring(1, closing - 1);
        if (!exe.EndsWith(".exe", StringComparison.OrdinalIgnoreCase))
            return (null, Array.Empty<string>());

        var rest = raw.Substring(closing + 1).Trim();
        var args = rest.Length == 0
            ? Array.Empty<string>()
            : rest.Split(' ', StringSplitOptions.RemoveEmptyEntries);
        return (exe, args);
    }

    /// <summary>Whether this uninstall entry is the Office suite itself.
    ///
    /// Pure. A machine carries several entries matching "Office" — an Extensibility
    /// Component, the Teams meeting add-in — and repairing one of those instead would do
    /// nothing at best. The suite is the one whose Modify command is Click-to-Run's.</summary>
    public static bool IsOfficeSuite(string? displayName, string? modifyPath)
    {
        if (string.IsNullOrWhiteSpace(displayName) || string.IsNullOrWhiteSpace(modifyPath))
            return false;
        if (modifyPath!.IndexOf("OfficeClickToRun.exe", StringComparison.OrdinalIgnoreCase) < 0)
            return false;
        return displayName!.IndexOf("Office", StringComparison.OrdinalIgnoreCase) >= 0
            || displayName.IndexOf("Microsoft 365", StringComparison.OrdinalIgnoreCase) >= 0;
    }

    /// <summary>The Modify command Windows would run for this machine's Office, or null.</summary>
    public static string? FindOfficeModifyPath()
    {
        foreach (var view in new[] { RegistryView.Registry64, RegistryView.Registry32 })
        {
            try
            {
                using var root = RegistryKey.OpenBaseKey(RegistryHive.LocalMachine, view);
                using var uninstall = root.OpenSubKey(UninstallKey);
                if (uninstall is null) continue;

                foreach (var name in uninstall.GetSubKeyNames())
                {
                    using var entry = uninstall.OpenSubKey(name);
                    if (entry is null) continue;
                    var modify = entry.GetValue("ModifyPath") as string;
                    if (IsOfficeSuite(entry.GetValue("DisplayName") as string, modify))
                        return modify;
                }
            }
            catch
            {
                // A view that cannot be read is not an answer; try the other one.
            }
        }
        return null;
    }

    public static (bool Success, string Output) Launch()
    {
        var modify = FindOfficeModifyPath();
        var (exe, args) = ParseModifyPath(modify);
        if (exe is null)
            return (false,
                "No Click-to-Run installation of Office was found on this PC, so there is no "
                + "built-in repair to open. Repair it from Settings > Apps if Office is "
                + "installed some other way.");

        try
        {
            var psi = new ProcessStartInfo
            {
                FileName = exe,
                Arguments = string.Join(" ", args),
                // Both are required. UseShellExecute is what allows a verb at all, and runas
                // is the programmatic form of right-click > Run as administrator: Office's
                // repair needs elevation, and the person's IT can authorise the prompt.
                UseShellExecute = true,
                Verb = "runas",
            };
            using var process = Process.Start(psi);
            if (process is null)
                return (false, "Windows did not start Office's repair.");

            return (true,
                "Office's repair window is now open on this PC. Choose Quick Repair and follow "
                + "the prompts — it closes every Office app while it runs, so save your work "
                + "first. If the crashes continue afterwards, Online Repair on the same screen "
                + "is the next step.");
        }
        catch (Win32Exception ex) when (ex.NativeErrorCode == 1223)   // ERROR_CANCELLED
        {
            // The UAC prompt was dismissed. Distinct from a failure to start: nothing is
            // wrong with the machine, someone simply declined, and saying so tells them
            // exactly what to do differently.
            return (false,
                "The administrator prompt was declined, so Office's repair did not open. "
                + "Run it again and approve the prompt — an administrator password is needed "
                + "because the repair changes the Office installation.");
        }
        catch (Exception ex)
        {
            return (false, "Could not open Office's repair: " + ex.Message);
        }
    }
}
