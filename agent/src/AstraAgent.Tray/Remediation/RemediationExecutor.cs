using System;
using System.Diagnostics;
using System.IO;
using System.Threading;
using System.Threading.Tasks;

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
                "clear_temp" => ClearTemp(),
                "clear_browser_cache" => ClearBrowserCache(),
                "restart_explorer" => RestartApp(new[] { "explorer" }, "explorer.exe"),
                "restart_outlook" => RestartApp(new[] { "OUTLOOK" }, "outlook.exe"),
                "restart_teams" => RestartApp(new[] { "ms-teams", "Teams" }, "ms-teams.exe"),
                "restart_zoom" => RestartApp(new[] { "Zoom" }, "Zoom.exe"),
                "restart_chrome" => RestartApp(new[] { "chrome" }, "chrome.exe"),
                "restart_edge" => RestartApp(new[] { "msedge" }, "msedge.exe"),
                "restart_application" => RestartApplication(parameters),
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

        foreach (var target in targets)
        {
            if (string.IsNullOrWhiteSpace(target) || !Directory.Exists(target)) continue;
            var full = Path.GetFullPath(target);
            if (!seen.Add(full)) continue;   // de-dupe (TMP/TEMP usually point to the same path)

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

        var mb = freed / 1024d / 1024d;
        var msg = $"Cleared temporary files — freed {mb:0.#} MB across {deleted} file(s).";
        if (inUse > 0)
            msg += $" {inUse} file(s) were in use by running apps and were skipped "
                 + "(close those apps and run it again to remove the rest).";
        return (true, msg);
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

        var mb = freed / 1024d / 1024d;
        var msg = $"Cleared browser cache — freed {mb:0.#} MB across {deleted} file(s).";
        if (inUse > 0)
            msg += $" {inUse} file(s) were locked by an open browser and were skipped "
                 + "(close the browser and run it again to clear the rest).";
        return (true, msg);
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

        var startTarget = capturedPath ?? fallbackExe;
        try
        {
            Process.Start(new ProcessStartInfo(startTarget) { UseShellExecute = true });
            return (true, killed > 0
                ? $"Closed {killed} instance(s) and relaunched the application."
                : "Launched the application.");
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
}
