using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Text.RegularExpressions;
using Microsoft.Win32;

namespace AstraAgent.Service.Remediation;

/// <summary>What the service would run to remove one installed application, and why.</summary>
public sealed record UninstallPlan(string FileName, IReadOnlyList<string> Arguments, string How);

/// <summary>Removes an application the organization has restricted.
///
/// This runs as LocalSystem in session 0, where NOTHING can be displayed. An uninstaller
/// that wants to ask "are you sure?" therefore waits on a window no human will ever see,
/// and the task hangs until it is killed. So the rule is absolute: run it only when it is
/// known to be silent, and otherwise refuse and say so. A refusal an administrator can read
/// is worth far more than a fix that appears to hang.
///
/// Three ways an uninstall is known to be silent, in order of confidence:
///   1. MSI — /qn is universal and vendor-independent.
///   2. QuietUninstallString — the vendor declared a silent command themselves.
///   3. KnownSilentSwitches — the documented switch for a specific product. Every entry
///      here is a claim about a real installer, so the list stays short and explicit
///      rather than guessing (an NSIS-looking uninstall.exe is NOT assumed to take /S).
///
/// Only HKLM is searched, both registry views. That matches what the telemetry collector
/// reports, so ASTRA never offers to remove something it could not see, and never fails to
/// find something it flagged. Per-user installs under HKCU are invisible to both.</summary>
public static class ApplicationUninstaller
{
    private static readonly string[] UninstallKeys =
    {
        @"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
        @"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
    };

    private static readonly Regex ProductCode = new(
        @"\{[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}\}",
        RegexOptions.Compiled);

    /// <summary>Products whose silent switch is documented but which do not publish a
    /// QuietUninstallString. Keyed by a marker that must appear in the UninstallString, so a
    /// match means we recognised THAT product's own uninstaller, not merely its name.</summary>
    private static readonly (string Marker, string[] Extra, string How)[] KnownSilentSwitches =
    {
        // Chrome's system-level uninstaller prompts unless --force-uninstall is passed.
        ("--uninstall", new[] { "--force-uninstall" }, "Chrome-style silent uninstall"),
    };

    /// <summary>Decides the command from what the registry recorded. Pure — no registry, no
    /// process — because this is the part that decides whether a machine is left alone or
    /// has software torn off it, and that decision deserves to be tested directly.</summary>
    public static (UninstallPlan? Plan, string? Refusal) PlanFor(
        string displayName, string? uninstallString, string? quietUninstallString)
    {
        var raw = (uninstallString ?? string.Empty).Trim();
        var quiet = (quietUninstallString ?? string.Empty).Trim();

        // 1. MSI: the product code is all that matters, and /qn is guaranteed silent.
        var source = raw.Length > 0 ? raw : quiet;
        if (source.IndexOf("msiexec", StringComparison.OrdinalIgnoreCase) >= 0)
        {
            var match = ProductCode.Match(source);
            if (!match.Success)
                return (null, $"'{displayName}' looks like an MSI but records no product code, "
                              + "so there is nothing safe to hand to msiexec.");
            return (new UninstallPlan(
                "msiexec.exe",
                new[] { "/x", match.Value, "/qn", "/norestart" },
                "Windows Installer (/qn)"), null);
        }

        // 2. The vendor's own silent command.
        if (quiet.Length > 0)
        {
            var (file, args) = SplitCommandLine(quiet);
            if (file.Length == 0)
                return (null, $"'{displayName}' records a silent uninstall command that could "
                              + "not be read.");
            return (new UninstallPlan(file, args, "vendor QuietUninstallString"), null);
        }

        if (raw.Length == 0)
            return (null, $"'{displayName}' records no uninstall command at all — it cannot be "
                          + "removed this way.");

        // 3. A product we know the documented switch for.
        foreach (var (marker, extra, how) in KnownSilentSwitches)
        {
            if (raw.IndexOf(marker, StringComparison.OrdinalIgnoreCase) < 0) continue;
            var (file, args) = SplitCommandLine(raw);
            if (file.Length == 0) break;
            var full = new List<string>(args);
            foreach (var e in extra)
            {
                // Do not pass the same switch twice if the string already carries it.
                if (!full.Exists(a => string.Equals(a, e, StringComparison.OrdinalIgnoreCase)))
                    full.Add(e);
            }
            return (new UninstallPlan(file, full, how), null);
        }

        return (null,
            $"'{displayName}' provides no silent uninstall command. Running its installer here "
            + "would open a window in a session with no desktop, where nobody could answer it, "
            + "so it has been left alone. Remove it through your software deployment tool.");
    }

    /// <summary>Splits a registry command line into an executable and its arguments.
    ///
    /// The path is usually quoted and usually contains spaces; when it is NOT quoted, the
    /// first token is the only defensible reading. Arguments are split on whitespace outside
    /// quotes and passed through ArgumentList, so nothing is ever handed to a shell.</summary>
    public static (string FileName, IReadOnlyList<string> Arguments) SplitCommandLine(string command)
    {
        var text = command.Trim();
        if (text.Length == 0) return (string.Empty, Array.Empty<string>());

        string file;
        int rest;
        if (text[0] == '"')
        {
            var close = text.IndexOf('"', 1);
            if (close < 0) return (string.Empty, Array.Empty<string>());
            file = text.Substring(1, close - 1);
            rest = close + 1;
        }
        else
        {
            var space = text.IndexOf(' ');
            file = space < 0 ? text : text.Substring(0, space);
            rest = space < 0 ? text.Length : space;
        }

        var args = new List<string>();
        var current = new System.Text.StringBuilder();
        var inQuotes = false;
        for (var i = rest; i < text.Length; i++)
        {
            var c = text[i];
            if (c == '"') { inQuotes = !inQuotes; continue; }
            if (char.IsWhiteSpace(c) && !inQuotes)
            {
                if (current.Length > 0) { args.Add(current.ToString()); current.Clear(); }
                continue;
            }
            current.Append(c);
        }
        if (current.Length > 0) args.Add(current.ToString());
        return (file, args);
    }

    /// <summary>Finds the application in HKLM and removes it. `appName` is matched as a
    /// case-insensitive substring of the registry DisplayName, because a policy list says
    /// "Google Chrome" while the machine says "Google Chrome 138.0.7204.51".</summary>
    public static (bool Success, string Output) Uninstall(string? appName)
    {
        var wanted = (appName ?? string.Empty).Trim();
        if (wanted.Length == 0) return (false, "No application name was given.");

        var found = FindInstalled(wanted);
        if (found is null)
            return (false, $"'{wanted}' is not installed for all users on this machine. "
                           + "A copy installed under a single user's profile is not visible "
                           + "here and cannot be removed this way.");

        var (displayName, uninstallString, quietString) = found.Value;
        var (plan, refusal) = PlanFor(displayName, uninstallString, quietString);
        if (plan is null) return (false, refusal ?? "No silent uninstall is available.");

        try
        {
            var psi = new ProcessStartInfo
            {
                FileName = plan.FileName,
                UseShellExecute = false,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                CreateNoWindow = true,
            };
            foreach (var a in plan.Arguments) psi.ArgumentList.Add(a);

            using var p = Process.Start(psi);
            if (p is null) return (false, $"Could not start the uninstaller for '{displayName}'.");

            // Ten minutes: a large suite can genuinely take that long, and anything beyond it
            // is a prompt nobody can answer rather than slow progress.
            if (!p.WaitForExit(600_000))
            {
                try { p.Kill(entireProcessTree: true); } catch { /* already gone */ }
                return (false, $"The uninstaller for '{displayName}' did not finish within ten "
                               + "minutes and was stopped. The application was probably waiting "
                               + "for a confirmation that cannot be shown here.");
            }

            var err = p.StandardError.ReadToEnd().Trim();
            var stdout = p.StandardOutput.ReadToEnd().Trim();
            var output = err.Length > 0 ? err : stdout;

            // Do not trust the exit code alone. Chrome's own uninstaller returns 19 from the
            // SYSTEM account over cosmetic shortcut-cleanup failures while genuinely removing
            // the program — the exact case that reported a successful removal as a failure and
            // put a scary error in front of an operator. The registry is the arbiter: read it
            // back and let whether the app is actually gone decide the verdict.
            var stillInstalled = FindInstalled(wanted) is not null;
            return Verdict(displayName, plan.How, p.ExitCode, stillInstalled, output);
        }
        catch (Exception ex)
        {
            return (false, $"Could not uninstall '{displayName}': {ex.Message}");
        }
    }

    /// <summary>Decides success from what the machine shows, not from the exit code — because
    /// the exit code lied. Pure, so the judgement that just misreported a real removal is the
    /// part under test.
    ///
    ///   still gone      → success, whatever the code (Chrome's 19 over cosmetic cleanup).
    ///   3010, gone      → success, restart to finish (some removers keep a stub until reboot,
    ///                     so a lingering entry after 3010 is not a failure — trust the code).
    ///   still installed → a real failure; the code and the uninstaller's own words explain it,
    ///                     and a "success" exit that left the app behind is called out as odd.</summary>
    public static (bool Success, string Output) Verdict(
        string displayName, string how, int exitCode, bool stillInstalled, string? errorText)
    {
        if (exitCode == 3010)
            return (true, $"Uninstalled {displayName} ({how}). Windows reports a restart is "
                          + "needed to finish removing it.");

        if (!stillInstalled)
            return (true, $"Uninstalled {displayName} ({how}).");

        var tail = string.IsNullOrWhiteSpace(errorText) ? string.Empty : " " + Truncate(errorText, 500);
        if (exitCode == 0)
            return (false,
                $"The uninstaller for {displayName} reported success, but it is still listed as "
                + "installed. It may need a reboot to finish, or a second copy is present." + tail);

        return (false,
            $"The uninstaller for {displayName} exited with code {exitCode} and it is still "
            + "installed." + tail);
    }

    private static (string DisplayName, string? UninstallString, string? QuietString)? FindInstalled(
        string wanted)
    {
        foreach (var view in new[] { RegistryView.Registry64, RegistryView.Registry32 })
        {
            using var baseKey = RegistryKey.OpenBaseKey(RegistryHive.LocalMachine, view);
            foreach (var keyPath in UninstallKeys)
            {
                using var root = baseKey.OpenSubKey(keyPath);
                if (root is null) continue;
                foreach (var subName in root.GetSubKeyNames())
                {
                    using var sub = root.OpenSubKey(subName);
                    var display = sub?.GetValue("DisplayName") as string;
                    if (string.IsNullOrWhiteSpace(display)) continue;
                    if (display.IndexOf(wanted, StringComparison.OrdinalIgnoreCase) < 0
                        && wanted.IndexOf(display, StringComparison.OrdinalIgnoreCase) < 0)
                        continue;
                    return (display,
                            sub?.GetValue("UninstallString") as string,
                            sub?.GetValue("QuietUninstallString") as string);
                }
            }
        }
        return null;
    }

    private static string Truncate(string s, int max) => s.Length <= max ? s : s[..max];
}
