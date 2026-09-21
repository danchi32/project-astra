using System;
using System.Diagnostics;
using System.IO;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging;
using Microsoft.Win32;

namespace AstraAgent.Service.Remediation;

/// <summary>Installs and removes the remote-support agent, on the backend's instruction.
///
/// Nothing about remote support ships inside the ASTRA installer, and that is deliberate.
/// The relay compiles and code-signs that agent itself, with the server URL, the device
/// group and the server's certificate hash already inside the executable — so a copy
/// vendored into ASTRA's installer would go stale against the relay's certificate, could
/// not carry a group id that differs per customer, and would put a remote-access binary on
/// the disk of every customer including those who never bought remote control.
///
/// So this device asks, and acts on the answer:
///
///   enabled  + not installed  -> download from the relay and install
///   disabled + installed      -> uninstall
///   anything else             -> do nothing
///
/// The second line matters as much as the first. A customer who stops paying for remote
/// control must stop having a remote-access service on their machines, not merely stop
/// being able to reach it.
///
/// Every failure here is logged and swallowed. This runs alongside the work the agent is
/// actually for, and a relay that is down, a proxy that blocks the download, or an
/// installer that returns non-zero must not stop telemetry or self-healing.</summary>
public sealed class RemoteSupportProvisioner
{
    private readonly ILogger logger;

    public RemoteSupportProvisioner(ILogger logger) => this.logger = logger;

    /// <summary>Bring this machine into line with `plan`. Returns whether anything changed.</summary>
    public async Task<bool> ApplyAsync(Api.RemoteSupportPlan plan, CancellationToken ct)
    {
        var installed = IsInstalled(plan.ServiceName ?? DefaultServiceName);

        if (plan.Enabled && !installed)
        {
            if (string.IsNullOrWhiteSpace(plan.DownloadUrl))
            {
                logger.LogWarning("Remote support enabled but no download URL was given");
                return false;
            }
            return await InstallAsync(plan.DownloadUrl!, ct);
        }

        if (!plan.Enabled && installed)
            return Uninstall(plan.ServiceName ?? DefaultServiceName);

        return false;
    }

    private const string DefaultServiceName = "AstraRemoteSupport";

    /// <summary>Whether the relay agent is on this machine.
    ///
    /// Read from the registry key the agent itself writes rather than from the service
    /// list, because that key is also where its node id lives — so "installed" and
    /// "identifiable" are the same question, answered from the same place. A service
    /// present without that key is a half-install, and treating it as absent lets the
    /// install below repair it.</summary>
    private static bool IsInstalled(string serviceName)
    {
        try
        {
            using var baseKey = RegistryKey.OpenBaseKey(RegistryHive.LocalMachine, RegistryView.Registry64);
            using var key = baseKey.OpenSubKey($@"SOFTWARE\Open Source\{serviceName}", writable: false);
            return key?.GetValue("NodeId") is string id && !string.IsNullOrWhiteSpace(id);
        }
        catch
        {
            return false;
        }
    }

    private async Task<bool> InstallAsync(string downloadUrl, CancellationToken ct)
    {
        // Under the agent's own directory, not %TEMP%. %TEMP% for LocalSystem is world
        // -writable in practice, and this file is about to be executed with full
        // privileges — a writable staging path is how that becomes somebody else's code.
        var dir = Path.Combine(AppContext.BaseDirectory, "remote-support");
        var exe = Path.Combine(dir, "AstraRemoteSupport.exe");

        try
        {
            Directory.CreateDirectory(dir);

            using (var http = new System.Net.Http.HttpClient { Timeout = TimeSpan.FromMinutes(5) })
            using (var response = await http.GetAsync(downloadUrl, ct))
            {
                response.EnsureSuccessStatusCode();
                await using var file = File.Create(exe);
                await response.Content.CopyToAsync(file, ct);
            }

            // A truncated download is an executable Windows will happily try to run.
            var size = new FileInfo(exe).Length;
            if (size < 1_000_000)
            {
                logger.LogWarning("Remote support download was only {Size} bytes; discarding", size);
                TryDelete(exe);
                return false;
            }

            var code = await RunAsync(exe, "-fullinstall", ct);
            if (code != 0)
            {
                logger.LogWarning("Remote support install exited with {Code}", code);
                return false;
            }

            logger.LogInformation("Remote support agent installed");
            return true;
        }
        catch (OperationCanceledException)
        {
            throw;
        }
        catch (Exception ex)
        {
            logger.LogWarning(ex, "Could not install the remote support agent");
            return false;
        }
    }

    private bool Uninstall(string serviceName)
    {
        // The relay agent copies itself out of wherever it was run from, so the copy that
        // can uninstall it is the installed one, not whatever is left in our staging
        // directory. Ask the service where it lives.
        var exe = InstalledExecutablePath(serviceName);
        if (exe is null)
        {
            logger.LogWarning("Remote support looks installed but its executable was not found");
            return false;
        }

        try
        {
            var code = RunAsync(exe, "-fulluninstall", CancellationToken.None).GetAwaiter().GetResult();
            if (code != 0)
            {
                logger.LogWarning("Remote support uninstall exited with {Code}", code);
                return false;
            }
            logger.LogInformation("Remote support agent removed (no longer entitled)");
            return true;
        }
        catch (Exception ex)
        {
            logger.LogWarning(ex, "Could not remove the remote support agent");
            return false;
        }
    }

    private static string? InstalledExecutablePath(string serviceName)
    {
        try
        {
            using var key = Registry.LocalMachine.OpenSubKey(
                $@"SYSTEM\CurrentControlSet\Services\{serviceName}", writable: false);
            // ImagePath is quoted when the path contains spaces, which Program Files does.
            var raw = (key?.GetValue("ImagePath") as string)?.Trim().Trim('"');
            return string.IsNullOrWhiteSpace(raw) || !File.Exists(raw) ? null : raw;
        }
        catch
        {
            return null;
        }
    }

    private static async Task<int> RunAsync(string exe, string args, CancellationToken ct)
    {
        using var process = new Process
        {
            StartInfo = new ProcessStartInfo(exe, args)
            {
                UseShellExecute = false,
                CreateNoWindow = true,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
            },
        };
        process.Start();
        // Drain both pipes; a child that fills one and blocks is a hang, not a failure,
        // and a hang here would stall the worker that calls this.
        var stdout = process.StandardOutput.ReadToEndAsync();
        var stderr = process.StandardError.ReadToEndAsync();
        await process.WaitForExitAsync(ct);
        await Task.WhenAll(stdout, stderr);
        return process.ExitCode;
    }

    private static void TryDelete(string path)
    {
        try { File.Delete(path); } catch { /* best effort */ }
    }
}
