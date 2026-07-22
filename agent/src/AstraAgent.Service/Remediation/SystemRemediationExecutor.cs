using System;
using System.Collections.Generic;
using System.IO;
using System.Security.AccessControl;
using System.Security.Principal;

namespace AstraAgent.Service.Remediation;

/// <summary>Executes machine-wide (elevated) remediation from a HARDCODED allowlist. The
/// backend only ever sends an action id — never a path or command — and the cleanup targets
/// below are fixed, well-known Windows folders resolved from the OS, never from server input.
/// This is the elevated counterpart to the Tray's user-session RemediationExecutor: it runs
/// as LocalSystem so it can clean C:\Windows\Temp and other machine caches the Tray can't.
/// Defense in depth: even a compromised backend can only ever trigger this one safe cleanup.</summary>
public sealed class SystemRemediationExecutor
{
    // The only actions the elevated service will ever perform. Everything else is refused.
    public static readonly IReadOnlySet<string> SupportedActions =
        new HashSet<string> { "clear_system_temp" };

    public (bool Success, string Output) Execute(string actionId)
    {
        try
        {
            return actionId switch
            {
                "clear_system_temp" => ClearSystemTemp(),
                _ => (false,
                    $"Action '{actionId}' is not a system-context action supported by the "
                    + "elevated service."),
            };
        }
        catch (Exception ex)
        {
            return (false, "Execution failed: " + ex.Message);
        }
    }

    /// <summary>Fixed, safe, machine-wide temp/cache folders. Each is a *subfolder* of a
    /// system root (never a drive root), so only its contents are cleared — the folder itself
    /// stays. Windows rebuilds every one of these on demand.</summary>
    private static IEnumerable<string> SystemTempTargets()
    {
        var windir = Environment.GetFolderPath(Environment.SpecialFolder.Windows);
        var programData = Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData);

        if (!string.IsNullOrWhiteSpace(windir))
        {
            yield return Path.Combine(windir, "Temp");                        // C:\Windows\Temp
            yield return Path.Combine(windir, "Prefetch");                    // C:\Windows\Prefetch
            yield return Path.Combine(windir, "SoftwareDistribution", "Download"); // WU cache
        }
        if (!string.IsNullOrWhiteSpace(programData))
        {
            var wer = Path.Combine(programData, "Microsoft", "Windows", "WER");
            yield return Path.Combine(wer, "ReportQueue");                    // error reports
            yield return Path.Combine(wer, "ReportArchive");
            yield return Path.Combine(wer, "Temp");
        }
    }

    /// <summary>A resolved target is only ever cleaned if it sits *under* the Windows or
    /// ProgramData root and is a real subfolder (never a drive root). This is a belt-and-braces
    /// guard against a tampered environment variable pointing a "temp" path at something else.</summary>
    private static bool IsSafeSystemTarget(string fullPath)
    {
        var windir = Environment.GetFolderPath(Environment.SpecialFolder.Windows);
        var programData = Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData);
        var full = Path.GetFullPath(fullPath).TrimEnd(Path.DirectorySeparatorChar);

        // Reject a drive root (e.g. "C:\") — must be a nested folder.
        var root = Path.GetPathRoot(full)?.TrimEnd(Path.DirectorySeparatorChar);
        if (string.IsNullOrEmpty(root) || string.Equals(full, root, StringComparison.OrdinalIgnoreCase))
            return false;

        bool Under(string baseDir) =>
            !string.IsNullOrWhiteSpace(baseDir)
            && full.StartsWith(
                Path.GetFullPath(baseDir).TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar,
                StringComparison.OrdinalIgnoreCase);

        return Under(windir) || Under(programData);
    }

    private static (bool, string) ClearSystemTemp()
    {
        long freed = 0;
        var deleted = 0;
        var inUse = 0;
        var locations = 0;
        var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);

        foreach (var target in SystemTempTargets())
        {
            if (string.IsNullOrWhiteSpace(target) || !Directory.Exists(target)) continue;
            var full = Path.GetFullPath(target);
            if (!seen.Add(full)) continue;
            if (!IsSafeSystemTarget(full)) continue;   // never delete outside the known roots

            locations++;

            foreach (var file in EnumerateFilesSafe(full))
            {
                try
                {
                    var info = new FileInfo(file);
                    var size = info.Length;
                    if (info.Attributes.HasFlag(FileAttributes.ReadOnly))
                        info.Attributes = FileAttributes.Normal;
                    info.Delete();
                    freed += size;
                    deleted++;
                }
                catch
                {
                    inUse++;   // locked / in use by Windows — skip, never force
                }
            }

            // Remove now-empty subdirectories bottom-up; leave the target folder itself.
            foreach (var dir in EnumerateDirsDeepestFirst(full))
            {
                try { Directory.Delete(dir, recursive: false); }
                catch { /* not empty or locked — leave it */ }
            }
        }

        var mb = freed / 1024d / 1024d;
        var msg = $"Deep-cleaned system temp — freed {mb:0.#} MB across {deleted} file(s) "
                + $"in {locations} system location(s).";
        if (inUse > 0)
            msg += $" {inUse} file(s) were in use by Windows and were left in place.";
        return (true, msg);
    }

    // TrustedInstaller — no WellKnownSidType, so matched by its fixed well-known value.
    private const string TrustedInstallerSid =
        "S-1-5-80-956008885-3418522649-1831038044-1853292631-2271478464";

    /// <summary>True only if <paramref name="dir"/> is owned by SYSTEM, Administrators or
    /// TrustedInstaller. This is the guard against a local-user junction/swap attack: because
    /// C:\Windows\Temp is user-writable, an unprivileged attacker could plant a directory
    /// junction to redirect this SYSTEM-level delete at C:\Windows\System32. Such a junction
    /// (and any directory the attacker controls) is owned by the attacker, so we refuse to
    /// descend into it. A SYSTEM/Admin-owned directory can't be replaced by a non-admin (they
    /// have no delete right on it), so the check-then-descend can't be raced. Unreadable owner
    /// → treated as untrusted (skip), never deleted.</summary>
    private static bool IsTrustedOwner(string dir)
    {
        try
        {
            var owner = new DirectoryInfo(dir).GetAccessControl()
                .GetOwner(typeof(SecurityIdentifier)) as SecurityIdentifier;
            if (owner is null) return false;
            return owner.IsWellKnown(WellKnownSidType.LocalSystemSid)
                || owner.IsWellKnown(WellKnownSidType.BuiltinAdministratorsSid)
                || owner.Value == TrustedInstallerSid;
        }
        catch
        {
            return false;   // can't read the owner → don't touch it
        }
    }

    /// <summary>A subdirectory is only walked if it is NOT a reparse point AND is owned by a
    /// trusted system principal — both must hold, re-checked at the moment of descent.</summary>
    private static bool SafeToDescend(string sub)
    {
        try
        {
            if (new DirectoryInfo(sub).Attributes.HasFlag(FileAttributes.ReparsePoint))
                return false;   // never follow a junction/symlink out of the tree
        }
        catch { return false; }
        return IsTrustedOwner(sub);
    }

    /// <summary>Enumerate every file under <paramref name="root"/> without throwing on an
    /// inaccessible subfolder, and without descending into reparse points or attacker-owned
    /// directories, so cleanup can never escape the target tree.</summary>
    private static IEnumerable<string> EnumerateFilesSafe(string root)
    {
        var stack = new Stack<string>();
        stack.Push(root);
        while (stack.Count > 0)
        {
            var dir = stack.Pop();

            string[] subdirs;
            try { subdirs = Directory.GetDirectories(dir); }
            catch { continue; }
            foreach (var sub in subdirs)
                if (SafeToDescend(sub)) stack.Push(sub);

            string[] files;
            try { files = Directory.GetFiles(dir); }
            catch { continue; }
            foreach (var file in files) yield return file;
        }
    }

    /// <summary>All safe-to-remove subdirectories under <paramref name="root"/>, deepest first,
    /// so they can be removed bottom-up once emptied.</summary>
    private static IEnumerable<string> EnumerateDirsDeepestFirst(string root)
    {
        var all = new List<string>();
        var stack = new Stack<string>();
        stack.Push(root);
        while (stack.Count > 0)
        {
            var dir = stack.Pop();
            string[] subdirs;
            try { subdirs = Directory.GetDirectories(dir); }
            catch { continue; }
            foreach (var sub in subdirs)
            {
                if (!SafeToDescend(sub)) continue;
                all.Add(sub);
                stack.Push(sub);
            }
        }
        all.Sort((a, b) => b.Length.CompareTo(a.Length));  // deeper paths first
        return all;
    }
}
