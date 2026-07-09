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
            "flush_dns", "clear_temp",
        };

    public async Task<(bool Success, string Output)> ExecuteAsync(string actionId, CancellationToken ct)
    {
        try
        {
            return actionId switch
            {
                "flush_dns" => await RunAsync("ipconfig", "/flushdns", ct),
                "clear_temp" => ClearTemp(),
                "restart_explorer" => RestartApp(new[] { "explorer" }, "explorer.exe"),
                "restart_outlook" => RestartApp(new[] { "OUTLOOK" }, "outlook.exe"),
                "restart_teams" => RestartApp(new[] { "ms-teams", "Teams" }, "ms-teams.exe"),
                "restart_zoom" => RestartApp(new[] { "Zoom" }, "Zoom.exe"),
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
        var temp = Path.GetTempPath();
        long freed = 0;
        var inUse = 0;
        foreach (var file in Directory.EnumerateFiles(temp))
        {
            try
            {
                var info = new FileInfo(file);
                var size = info.Length;
                info.Delete();
                freed += size;
            }
            catch
            {
                inUse++;
            }
        }
        foreach (var dir in Directory.EnumerateDirectories(temp))
        {
            try { Directory.Delete(dir, recursive: true); }
            catch { inUse++; }
        }
        return (true, $"Cleared temporary files (~{freed / 1024 / 1024} MB freed; {inUse} in use, skipped).");
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
