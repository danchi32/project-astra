using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Text.RegularExpressions;

namespace AstraAgent.Service.Remediation;

/// <summary>Installs one software package with winget, machine-wide (A2).
///
/// The id has already been checked against the server's catalog; the agent checks it AGAIN
/// against its own copy (`Catalog`), so a compromised or buggy backend can't install anything
/// else as SYSTEM — the CLAUDE.md "agent runs only allowlisted things" rule. The backend test
/// `test_agent_catalog_matches` keeps the two lists equal. It is passed as one argv element,
/// never through a shell.
///
/// winget ships as a per-user Store app, so LocalSystem has no `winget` on its PATH. The
/// executable is found in the machine-wide WindowsApps folder instead (newest version wins).
/// Machines without App Installer (Windows 10 LTSC, Server) get a clear "not available".</summary>
public static class PackageInstaller
{
    private static readonly Regex IdOk = new(@"^[A-Za-z0-9][A-Za-z0-9.+_-]{1,99}$", RegexOptions.Compiled);

    /// <summary>Mirrors backend/app/services/software_catalog.py CATALOG. Adding a package
    /// means adding it in both places and shipping an agent release.</summary>
    internal static readonly HashSet<string> Catalog = new(StringComparer.Ordinal)
    {
        "Google.Chrome", "Mozilla.Firefox", "Microsoft.Edge", "Zoom.Zoom", "Microsoft.Teams",
        "SlackTechnologies.Slack", "Microsoft.Office", "Adobe.Acrobat.Reader.64-bit",
        "Foxit.FoxitReader", "Notepad++.Notepad++", "7zip.7zip", "VideoLAN.VLC",
        "Microsoft.PowerToys", "Google.GoogleDrive", "Dropbox.Dropbox",
        "Microsoft.VisualStudioCode", "Git.Git", "Python.Python.3.12",
    };
    private static readonly TimeSpan Timeout = TimeSpan.FromMinutes(45);

    public static (bool, string) Install(string? packageId)
    {
        var id = (packageId ?? string.Empty).Trim();
        if (!IdOk.IsMatch(id) || !id.Contains('.'))
            return (false, $"'{packageId}' is not a valid package id.");
        if (!Catalog.Contains(id))
            return (false, $"'{id}' is not in this agent's software catalog, so it wasn't installed.");

        var winget = FindWinget();
        if (winget is null)
            return (false, "winget (App Installer) is not available on this PC, so SAVIO can't "
                           + "install software here. It ships with Windows 10 1809+ and 11; LTSC "
                           + "and Server editions need it added.");

        var (code, output) = Run(winget, "install", "--id", id, "--exact", "--scope", "machine",
            "--silent", "--accept-package-agreements", "--accept-source-agreements",
            "--disable-interactivity", "--source", "winget");
        return Describe(code, id, output);
    }

    internal static (bool, string) Describe(int code, string id, string output)
    {
        var tail = string.Join(" ", output.Split('\n').Select(l => l.Trim())
            .Where(l => l.Length > 0 && !l.All(c => "-\\|/ █▒".Contains(c))).TakeLast(3));
        return unchecked((uint)code) switch
        {
            0 => (true, $"Installed {id}."),
            // Already present at the newest version — the goal state, not a failure.
            0x8A15002B => (true, $"{id} is already installed and up to date."),
            0x8A150061 => (true, $"{id} is already installed."),
            0x8A150014 => (false, $"winget couldn't find '{id}' in its catalog."),
            0x8A150011 => (false, "winget's package source couldn't be reached — check internet access."),
            // Seen on a real laptop: winget ran fine as SYSTEM and found the package, then the
            // installer download (GitHub releases) timed out — from the user's session too, so
            // the network, not the account, was the cause. Say exactly that much.
            0x80072EE2 or 0x80072EFD or 0x80072EE7 =>
                (false, $"Installing {id} failed: the installer couldn't be downloaded (connection "
                        + "timed out). Something on this PC's network — a firewall, proxy or security "
                        + "tool — is blocking the download site."),
            0x8A150101 => (false, $"{id} has no machine-wide installer, so it can't be pushed to all users."),
            _ => (false, $"Installing {id} failed (winget exit 0x{code:X8}). {tail}".Trim()),
        };
    }

    internal static string? FindWinget()
    {
        try
        {
            var apps = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles), "WindowsApps");
            var arch = System.Runtime.InteropServices.RuntimeInformation.OSArchitecture
                == System.Runtime.InteropServices.Architecture.Arm64 ? "arm64" : "x64";
            // Newest by real version: as text, "1.9" sorts above "1.10".
            return Directory.GetDirectories(apps, $"Microsoft.DesktopAppInstaller_*_{arch}__8wekyb3d8bbwe")
                .Select(d => (dir: d, version: VersionOf(d)))
                .Where(x => File.Exists(Path.Combine(x.dir, "winget.exe")))
                .OrderByDescending(x => x.version)
                .Select(x => Path.Combine(x.dir, "winget.exe"))
                .FirstOrDefault();
        }
        catch
        {
            return null;   // WindowsApps is ACL'd; a non-SYSTEM caller may not list it
        }
    }

    internal static Version VersionOf(string dir)
    {
        var parts = Path.GetFileName(dir).Split('_');
        return parts.Length > 1 && Version.TryParse(parts[1], out var v) ? v : new Version(0, 0);
    }

    private static (int, string) Run(string exe, params string[] args)
    {
        var psi = new ProcessStartInfo
        {
            FileName = exe,
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            CreateNoWindow = true,
        };
        foreach (var a in args) psi.ArgumentList.Add(a);
        // winget stages the downloaded installer under %TEMP%. SYSTEM's is C:\Windows\Temp,
        // where any user can create the staging folder first and swap the installer between
        // winget's hash check and its launch. Give it a temp only SYSTEM/Administrators can write.
        var temp = Path.Combine(AstraAgent.Service.Security.SecureDirectory.StateRoot, "winget-temp");
        AstraAgent.Service.Security.SecureDirectory.Ensure(temp);
        psi.Environment["TEMP"] = temp;
        psi.Environment["TMP"] = temp;
        using var p = Process.Start(psi)!;
        var stdout = p.StandardOutput.ReadToEndAsync();
        var stderr = p.StandardError.ReadToEndAsync();
        if (!p.WaitForExit((int)Timeout.TotalMilliseconds))
        {
            try { p.Kill(entireProcessTree: true); } catch { /* best effort */ }
            return (-1, "Timed out after 45 minutes.");
        }
        return (p.ExitCode, stdout.Result + "\n" + stderr.Result);
    }
}
