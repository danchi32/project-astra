using System;
using System.Diagnostics;
using System.IO;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Win32;

namespace AstraAgent.Tray.Remediation;

/// <summary>Executes remediation actions from a HARDCODED allowlist. The server sends an
/// action id (never a command string); anything without a handler here is refused. Handlers
/// only perform user-session-safe operations — elevated actions are reported as unsupported.</summary>
public sealed class RemediationExecutor
{
    // The only actions this desktop agent will ever perform. Everything else is refused.
    public static readonly System.Collections.Generic.IReadOnlySet<string> SupportedActions =
        new System.Collections.Generic.HashSet<string>
        {
            "restart_explorer", "restart_outlook", "restart_teams", "restart_zoom",
            "restart_chrome", "restart_edge", "restart_application",
            "flush_dns", "clear_temp", "clear_browser_cache",
            "create_outlook_rule", "add_network_printer",
        };

    public async Task<(bool Success, string Output)> ExecuteAsync(
        string actionId,
        System.Collections.Generic.IReadOnlyDictionary<string, string>? parameters,
        CancellationToken ct)
    {
        try
        {
            return actionId switch
            {
                "flush_dns" => await RunAsync("ipconfig", "/flushdns", ct),
                "add_network_printer" => await AddNetworkPrinterAsync(
                    parameters is not null && parameters.TryGetValue("printer_path", out var pp) ? pp : null, ct),
                "clear_temp" => ClearTemp(),
                "clear_browser_cache" => ClearBrowserCache(),
                "restart_explorer" => RestartApp(new[] { "explorer" }, "explorer.exe"),
                "restart_outlook" => RestartApp(new[] { "OUTLOOK" }, "outlook.exe"),
                "restart_teams" => RestartApp(new[] { "ms-teams", "Teams" }, "ms-teams.exe"),
                "restart_zoom" => RestartApp(new[] { "Zoom" }, "Zoom.exe"),
                "restart_chrome" => RestartApp(new[] { "chrome" }, "chrome.exe"),
                "restart_edge" => RestartApp(new[] { "msedge" }, "msedge.exe"),
                "restart_application" => RestartApplication(parameters),
                "create_outlook_rule" => CreateOutlookRule(parameters),
                _ => (false,
                    $"Action '{actionId}' is not supported by the desktop agent "
                    + "(it may require the elevated service, which is a later phase)."),
            };
        }
        catch (Exception ex)
        {
            return (false, "Execution failed: " + ex.Message);
        }
    }

    private static (bool, string) RestartApplication(
        System.Collections.Generic.IReadOnlyDictionary<string, string>? parameters)
    {
        var process = parameters is not null && parameters.TryGetValue("process_name", out var p)
            ? p?.Trim()
            : null;
        if (string.IsNullOrWhiteSpace(process))
            return (false, "No application was specified to restart.");

        // Normalize: callers may send "WINWORD.exe" or "WINWORD".
        if (process.EndsWith(".exe", StringComparison.OrdinalIgnoreCase))
            process = process[..^4];
        return RestartApp(new[] { process }, process + ".exe");
    }

    /// <summary>Resolve an app's full path from the Windows "App Paths" registry (used by
    /// ShellExecute), so a not-currently-running app like Excel launches reliably by name.
    /// Falls back to the bare name if there's no registered path.</summary>
    private static string ResolveLaunchTarget(string exeName)
    {
        foreach (var root in new[] { Registry.LocalMachine, Registry.CurrentUser })
        {
            try
            {
                using var key = root.OpenSubKey(
                    @"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\" + exeName);
                if (key?.GetValue(null) is string raw)
                {
                    var path = raw.Trim().Trim('"');
                    if (path.Length > 0 && File.Exists(path))
                        return path;
                }
            }
            catch { /* registry unavailable — fall through to the bare name */ }
        }
        return exeName;
    }

    /// <summary>Connects this user to a shared printer.
    ///
    /// It runs here, in the signed-in person's session, because a printer connection lives in
    /// their profile — the same command run by the elevated service would attach the printer
    /// to LocalSystem, where nobody can print to it, and report success.
    ///
    /// The common failure is not a wrong path. Since the PrintNightmare hardening, installing
    /// a print driver needs administrator rights, so this succeeds when the driver is already
    /// present and is refused when it is not. That refusal is passed on in those words rather
    /// than as a bare error code, because the answer to it is to deploy the driver, not to
    /// try again.</summary>
    private static async Task<(bool, string)> AddNetworkPrinterAsync(
        string? printerPath, CancellationToken ct)
    {
        var path = (printerPath ?? string.Empty).Trim();
        if (path.Length == 0) return (false, "No printer path was given.");

        var psi = new ProcessStartInfo
        {
            FileName = "rundll32.exe",
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
            CreateNoWindow = true,
        };
        psi.ArgumentList.Add("printui.dll,PrintUIEntry");
        psi.ArgumentList.Add("/in");    // install a network printer connection
        psi.ArgumentList.Add("/q");     // no UI: there may be nobody watching
        psi.ArgumentList.Add("/n");
        psi.ArgumentList.Add(path);     // one argv element — never a shell string

        using var proc = Process.Start(psi);
        if (proc is null) return (false, "Could not start the printer installer.");
        var stdout = await proc.StandardOutput.ReadToEndAsync(ct);
        var stderr = await proc.StandardError.ReadToEndAsync(ct);
        await proc.WaitForExitAsync(ct);

        if (proc.ExitCode == 0)
            return (true, $"Connected to {path}. It should now appear in your printer list.");

        var text = (string.IsNullOrWhiteSpace(stderr) ? stdout : stderr).Trim();
        return (false,
            $"Windows would not connect to {path}. This is usually one of: the printer name is "
            + "wrong, you do not have permission to it, or its driver is not installed on this "
            + "PC — since a Windows security update, installing a print driver needs an "
            + "administrator."
            + (text.Length > 0 ? " " + text : string.Empty));
    }

    private static async Task<(bool, string)> RunAsync(string exe, string args, CancellationToken ct)
    {
        var psi = new ProcessStartInfo(exe, args)
        {
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
            CreateNoWindow = true,
        };
        using var proc = Process.Start(psi)
            ?? throw new InvalidOperationException($"Could not start {exe}.");
        var stdout = await proc.StandardOutput.ReadToEndAsync(ct);
        var stderr = await proc.StandardError.ReadToEndAsync(ct);
        await proc.WaitForExitAsync(ct);
        var text = string.IsNullOrWhiteSpace(stdout) ? stderr : stdout;
        return (proc.ExitCode == 0, text.Trim());
    }

    private static (bool, string) ClearTemp()
    {
        // Clean the standard user-writable temp locations. Windows\Temp and other
        // machine-wide caches need elevation and are left to the (future) service.
        var targets = new[]
        {
            Path.GetTempPath(),                                              // %TEMP%
            Environment.GetEnvironmentVariable("TMP"),
            Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "Temp"),                                                     // %LocalAppData%\Temp
        };

        long freed = 0;
        var deleted = 0;
        var inUse = 0;
        var seen = new System.Collections.Generic.HashSet<string>(StringComparer.OrdinalIgnoreCase);
        var cleaned = new System.Collections.Generic.List<string>();

        foreach (var target in targets)
        {
            if (string.IsNullOrWhiteSpace(target) || !Directory.Exists(target)) continue;
            var full = Path.GetFullPath(target);
            if (!seen.Add(full)) continue;   // de-dupe (TMP/TEMP usually point to the same path)
            cleaned.Add(full);

            // Delete files individually and recursively, so a single locked file no
            // longer causes an entire subtree to be skipped (the previous bug).
            foreach (var file in EnumerateFilesSafe(full))
            {
                try
                {
                    var info = new FileInfo(file);
                    var size = info.Length;
                    // Clear read-only/hidden attributes so those files delete too.
                    if (info.Attributes.HasFlag(FileAttributes.ReadOnly))
                        info.Attributes = FileAttributes.Normal;
                    info.Delete();
                    freed += size;
                    deleted++;
                }
                catch
                {
                    inUse++;
                }
            }

            // Remove the now-empty subdirectories (bottom-up); ignore any still holding
            // locked files.
            foreach (var dir in EnumerateDirsDeepestFirst(full))
            {
                try { Directory.Delete(dir, recursive: false); }
                catch { /* not empty or locked — leave it */ }
            }
        }

        // Name the folder and the account. %TEMP% is per-user, so "freed 332 MB" is
        // unverifiable — and actively misleading — unless you can see WHOSE temp was
        // emptied. If this process isn't running as the signed-in user (for example it was
        // started by an installer running under an admin account, before the first logon
        // hands it to the real user), it cleans that account's temp and the user sees no
        // change at all. Saying which path and which identity makes that self-evident
        // instead of a mystery.
        var who = Environment.UserName;
        return ClearVerdict(
            $"temporary files for {who}",
            cleaned.Count > 0 ? $" in {string.Join(", ", cleaned)}" : "",
            deleted, inUse, freed,
            foundAnything: cleaned.Count > 0,
            blockedBy: "");
    }

    private static (bool, string) ClearBrowserCache()
    {
        var local = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        var roaming = Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData);

        // Only ever HTTP/render caches — never History, Cookies, Login Data, Bookmarks or
        // profile data. Chromium browsers keep caches in per-profile subfolders under
        // "User Data"; Firefox under each profile's "cache2".
        var cacheDirs = new System.Collections.Generic.List<string>();

        void AddChromium(string userData)
        {
            if (!Directory.Exists(userData)) return;
            string[] profiles;
            try { profiles = Directory.GetDirectories(userData); }
            catch { return; }
            foreach (var profile in profiles)
            {
                foreach (var name in new[] { "Cache", "Code Cache", "GPUCache", "ShaderCache",
                                             Path.Combine("Service Worker", "CacheStorage") })
                {
                    var dir = Path.Combine(profile, name);
                    if (Directory.Exists(dir)) cacheDirs.Add(dir);
                }
            }
        }

        AddChromium(Path.Combine(local, "Google", "Chrome", "User Data"));
        AddChromium(Path.Combine(local, "Microsoft", "Edge", "User Data"));
        AddChromium(Path.Combine(local, "BraveSoftware", "Brave-Browser", "User Data"));

        // Firefox: %AppData%\Mozilla\Firefox\Profiles\<profile>\cache2 lives under LocalAppData.
        var ffProfiles = Path.Combine(local, "Mozilla", "Firefox", "Profiles");
        if (Directory.Exists(ffProfiles))
        {
            try
            {
                foreach (var profile in Directory.GetDirectories(ffProfiles))
                {
                    var dir = Path.Combine(profile, "cache2");
                    if (Directory.Exists(dir)) cacheDirs.Add(dir);
                }
            }
            catch { /* ignore */ }
        }
        _ = roaming;  // reserved; Firefox roaming profile also possible but rare

        if (cacheDirs.Count == 0)
            return (true, "No browser cache folders were found to clear.");

        long freed = 0;
        var deleted = 0;
        var inUse = 0;
        foreach (var dir in cacheDirs)
        {
            foreach (var file in EnumerateFilesSafe(dir))
            {
                try
                {
                    var info = new FileInfo(file);
                    var size = info.Length;
                    info.Delete();
                    freed += size;
                    deleted++;
                }
                catch { inUse++; }
            }
        }

        return ClearVerdict("browser cache", "", deleted, inUse, freed,
                            foundAnything: true, blockedBy: RunningBrowsers());
    }

    /// <summary>Whether a file-clearing action actually achieved anything, and what to say.
    ///
    /// Pure, and deliberately separate from the deleting, because this judgement is the part
    /// that was wrong: both clearing actions used to return success unconditionally. With a
    /// browser open every cache delete fails — Chromium memory-maps those files — so the
    /// ordinary case produced "freed 0 MB across 0 file(s)" and still reported a fix. Having
    /// run without crashing is not the same as having cleared anything.</summary>
    /// <param name="what">Noun for the message, e.g. "browser cache".</param>
    /// <param name="where">Optional location clause, already spaced, e.g. " in C:\Temp".</param>
    /// <param name="foundAnything">False when there was nothing on disk to clear at all —
    /// genuinely nothing to do, which is a success, unlike being unable to do it.</param>
    /// <param name="blockedBy">What holds the files, when known, e.g. "Google Chrome".</param>
    public static (bool Success, string Message) ClearVerdict(
        string what, string where, int deleted, int lockedOut, long freedBytes,
        bool foundAnything, string blockedBy)
    {
        var holder = string.IsNullOrEmpty(blockedBy) ? "a running application" : blockedBy;

        if (!foundAnything)
            return (true, $"No {what} was found to clear.");

        // Nothing removed and everything locked: the action did not happen. Saying so is the
        // only way the user learns what to do about it.
        if (deleted == 0 && lockedOut > 0)
            return (false,
                $"Could not clear the {what} — all {lockedOut} file(s){where} are locked by "
                + $"{holder}. Close it and run this again.");

        var mb = freedBytes / 1024d / 1024d;
        var msg = $"Cleared the {what} — freed {mb:0.#} MB across {deleted} file(s){where}.";
        if (lockedOut > 0)
            msg += $" {lockedOut} file(s) were locked by {holder} and were skipped "
                 + "(close it and run this again to clear the rest).";
        return (true, msg);
    }

    /// <summary>Names the browsers running right now, so "close it and try again" can say
    /// which one. Empty when none are — the caller then falls back to a generic phrase.</summary>
    private static string RunningBrowsers()
    {
        var known = new[]
        {
            ("chrome", "Google Chrome"), ("msedge", "Microsoft Edge"),
            ("brave", "Brave"), ("firefox", "Firefox"),
        };
        var found = new System.Collections.Generic.List<string>();
        foreach (var (process, label) in known)
        {
            // Enumeration races process exit; a name that vanishes is not an error.
            try { if (Process.GetProcessesByName(process).Length > 0) found.Add(label); }
            catch { /* ignore */ }
        }
        return string.Join(" and ", found);
    }

    /// <summary>Enumerate every file under <paramref name="root"/> without throwing when a
    /// subfolder is inaccessible (unauthorized/locked directories are skipped, not fatal).</summary>
    private static System.Collections.Generic.IEnumerable<string> EnumerateFilesSafe(string root)
    {
        var stack = new System.Collections.Generic.Stack<string>();
        stack.Push(root);
        while (stack.Count > 0)
        {
            var dir = stack.Pop();
            string[] subdirs;
            try { subdirs = Directory.GetDirectories(dir); }
            catch { continue; }
            foreach (var sub in subdirs) stack.Push(sub);

            string[] files;
            try { files = Directory.GetFiles(dir); }
            catch { continue; }
            foreach (var file in files) yield return file;
        }
    }

    /// <summary>All subdirectories under <paramref name="root"/>, deepest first, so they can be
    /// removed bottom-up once emptied.</summary>
    private static System.Collections.Generic.IEnumerable<string> EnumerateDirsDeepestFirst(string root)
    {
        System.Collections.Generic.List<string> all;
        try { all = new System.Collections.Generic.List<string>(
            Directory.GetDirectories(root, "*", SearchOption.AllDirectories)); }
        catch { yield break; }
        all.Sort((a, b) => b.Length.CompareTo(a.Length));  // longer paths (deeper) first
        foreach (var dir in all) yield return dir;
    }

    private static (bool, string) RestartApp(string[] processNames, string fallbackExe)
    {
        string? capturedPath = null;
        var killed = 0;
        foreach (var name in processNames)
        {
            foreach (var proc in Process.GetProcessesByName(name))
            {
                try { capturedPath ??= proc.MainModule?.FileName; }
                catch { /* access denied on some processes — ignore */ }
                try
                {
                    proc.Kill();
                    proc.WaitForExit(3000);
                    killed++;
                }
                catch { /* already gone */ }
                finally { proc.Dispose(); }
            }
        }

        var startTarget = capturedPath ?? ResolveLaunchTarget(fallbackExe);
        try
        {
            Process.Start(new ProcessStartInfo(startTarget) { UseShellExecute = true });
            return (true, killed > 0
                ? $"Closed {killed} instance(s) and relaunched the application ({startTarget})."
                : $"Launched the application ({startTarget}).");
        }
        catch (Exception ex)
        {
            // Closing a hung app is itself a useful heal; only the relaunch failed.
            return (killed > 0,
                killed > 0
                    ? $"Closed the application, but couldn't relaunch it automatically ({ex.Message}). Please reopen it."
                    : $"The application wasn't running and couldn't be launched ({ex.Message}).");
        }
    }

    /// <summary>Creates a rule in the user's DESKTOP Outlook that moves incoming mail from a
    /// given sender into a folder (created under the Inbox if missing). Late-bound COM, so no
    /// Office interop assembly is required. Runs in the user session where the tray app lives,
    /// which is where an Outlook profile is available. The backend has already validated the
    /// address + folder name.</summary>
    private static (bool, string) CreateOutlookRule(
        System.Collections.Generic.IReadOnlyDictionary<string, string>? parameters)
    {
        var from = parameters is not null && parameters.TryGetValue("from_address", out var f) ? f?.Trim() : null;
        var folderName = parameters is not null && parameters.TryGetValue("folder_name", out var fn) ? fn?.Trim() : null;
        if (string.IsNullOrWhiteSpace(from))
            return (false, "No sender address was provided for the rule.");
        if (string.IsNullOrWhiteSpace(folderName))
            return (false, "No target folder was provided for the rule.");

        var progId = Type.GetTypeFromProgID("Outlook.Application");
        if (progId is null)
            return (false, "Microsoft Outlook (desktop) doesn't appear to be installed on this machine.");

        object? outlook = null;
        try
        {
            outlook = Activator.CreateInstance(progId);
            dynamic app = outlook!;
            dynamic session = app.Session;                 // MAPI namespace
            dynamic inbox = session.GetDefaultFolder(6);   // olFolderInbox

            // Find (case-insensitive) or create the destination folder under the Inbox.
            dynamic? target = null;
            dynamic folders = inbox.Folders;
            for (int i = 1; i <= (int)folders.Count; i++)
            {
                dynamic folder = folders[i];
                if (string.Equals((string)folder.Name, folderName, StringComparison.OrdinalIgnoreCase))
                {
                    target = folder;
                    break;
                }
            }
            target ??= folders.Add(folderName);

            // from <address>  ->  move to <folder>
            dynamic rules = session.DefaultStore.GetRules();
            string ruleName = $"ASTRA: {from} -> {folderName}";
            dynamic rule = rules.Create(ruleName, 0);      // olRuleReceive

            dynamic senderCond = rule.Conditions.SenderAddress;
            senderCond.Enabled = true;
            senderCond.Address = new object[] { from };    // Outlook expects a variant array

            dynamic moveAction = rule.Actions.MoveToFolder;
            moveAction.Enabled = true;
            moveAction.Folder = target;

            rules.Save(false);                             // don't pop the rules-in-error dialog
            return (true, $"Created the Outlook rule '{ruleName}'. Mail from {from} will now move to '{folderName}'.");
        }
        catch (Exception ex)
        {
            return (false, "Couldn't create the Outlook rule: " + ex.Message
                + " (Outlook desktop must be installed with a configured mail profile.)");
        }
        finally
        {
            if (outlook is not null && System.Runtime.InteropServices.Marshal.IsComObject(outlook))
                System.Runtime.InteropServices.Marshal.ReleaseComObject(outlook);
        }
    }
}
