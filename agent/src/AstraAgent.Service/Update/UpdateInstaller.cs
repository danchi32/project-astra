using System.Diagnostics;
using System.IO.Compression;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;

namespace AstraAgent.Service.Update;

/// <summary>Downloads a signature-verified release, checks its hash, and applies it.
///
/// A running Windows service holds its own binaries locked, so the file swap can't happen
/// in-process. Instead we stage the new files, launch a tiny self-deleting batch script, and
/// stop the service; the script waits for our process to exit, copies the new files over the
/// install directory (preserving local appsettings.json), and restarts the service.</summary>
public sealed class UpdateInstaller(ILogger<UpdateInstaller> logger)
{
    private const string ServiceName = "AstraAgent";

    // Local config written at install time (server URL, enrollment) must survive an update.
    private static readonly string[] PreservedFiles = { "appsettings.json" };

    private readonly string _installDir = AppContext.BaseDirectory.TrimEnd('\\');
    // Admin-only working area (see UpdatePaths) — never a world-writable ProgramData path.
    private readonly string _workRoot = UpdatePaths.WorkRoot;

    /// <summary>Fetch + verify + stage the release, then hand off to the apply script and ask the
    /// host to stop so the files unlock. Returns false (and changes nothing) on any failure.</summary>
    public async Task<bool> ApplyAsync(
        UpdateManifest manifest, IHostApplicationLifetime lifetime, CancellationToken ct)
    {
        var staging = Path.Combine(_workRoot, "staging", manifest.Version);
        var zipPath = Path.Combine(_workRoot, $"AstraAgent-{manifest.Version}.zip");
        try
        {
            // Lock the working area down before we write anything executable into it. If it
            // can't be secured, abort — better no update than a SYSTEM-writable staging dir.
            UpdatePaths.EnsureHardened();

            if (!await DownloadAsync(manifest.Url, zipPath, ct))
                return false;

            if (!UpdateVerifier.FileMatchesHash(zipPath, manifest.Sha256))
            {
                logger.LogWarning("Update {Version} rejected: SHA-256 mismatch", manifest.Version);
                TryDelete(zipPath);
                return false;
            }

            // Fresh staging dir each time so a half-extracted prior attempt can't leak in.
            if (Directory.Exists(staging))
                Directory.Delete(staging, recursive: true);
            Directory.CreateDirectory(staging);
            ZipFile.ExtractToDirectory(zipPath, staging);
            TryDelete(zipPath);

            // Sanity: the package must actually contain the service binary.
            if (!File.Exists(Path.Combine(staging, "AstraAgent.Service.exe"))
                && !File.Exists(Path.Combine(staging, "AstraAgent.Service.dll")))
            {
                logger.LogWarning("Update {Version} rejected: package missing agent binary", manifest.Version);
                return false;
            }

            LaunchApplyScript(staging);
            logger.LogInformation(
                "Update {Version} staged; restarting to apply.", manifest.Version);

            // Let the script take over: stopping the host unlocks our files.
            lifetime.StopApplication();
            return true;
        }
        catch (Exception ex)
        {
            logger.LogError(ex, "Failed to apply update {Version}", manifest.Version);
            return false;
        }
    }

    private async Task<bool> DownloadAsync(string url, string destPath, CancellationToken ct)
    {
        try
        {
            using var client = new HttpClient { Timeout = TimeSpan.FromMinutes(10) };
            using var response = await client.GetAsync(
                url, HttpCompletionOption.ResponseHeadersRead, ct);
            if (!response.IsSuccessStatusCode)
            {
                logger.LogWarning("Update download failed: {Status} from {Url}", response.StatusCode, url);
                return false;
            }
            await using var src = await response.Content.ReadAsStreamAsync(ct);
            await using var dst = File.Create(destPath);
            await src.CopyToAsync(dst, ct);
            return true;
        }
        catch (Exception ex)
        {
            logger.LogWarning(ex, "Update download from {Url} failed", url);
            return false;
        }
    }

    private void LaunchApplyScript(string staging)
    {
        // The service is hosted by dotnet.exe, so the PID we wait on is that host — we must
        // match on the PID NUMBER, not an image name (the image is "dotnet.exe", not "Astra…").
        var pid = Environment.ProcessId;
        var scriptPath = Path.Combine(_workRoot, "apply-update.cmd");
        var excludes = string.Join(" ", PreservedFiles.Select(f => $"\"{f}\""));

        // The script polls (via CSV output that reliably contains the PID field) until our host
        // process exits and unlocks the files, mirrors the new files in while preserving local
        // config, restarts the service with a few retries in case the SCM is still settling, and
        // finally deletes itself. robocopy exit codes < 8 are success, so its failure isn't fatal.
        var script = $"""
            @echo off
            setlocal enabledelayedexpansion
            :wait
            tasklist /FI "PID eq {pid}" /NH /FO CSV 2>nul | findstr /C:"\"{pid}\"" >nul
            if not errorlevel 1 (
                timeout /t 1 /nobreak >nul
                goto wait
            )
            robocopy "{staging}" "{_installDir}" /E /R:3 /W:2 /XF {excludes} >nul
            set /a tries=0
            :startsvc
            sc start {ServiceName} >nul 2>&1
            sc query {ServiceName} | findstr /I "RUNNING START_PENDING" >nul && goto started
            set /a tries+=1
            if !tries! lss 5 ( timeout /t 2 /nobreak >nul & goto startsvc )
            :started
            rmdir /S /Q "{staging}" >nul 2>&1
            del "%~f0" >nul 2>&1
            """;
        File.WriteAllText(scriptPath, script);

        Process.Start(new ProcessStartInfo
        {
            FileName = "cmd.exe",
            Arguments = $"/c \"{scriptPath}\"",
            WorkingDirectory = _workRoot,
            UseShellExecute = false,
            CreateNoWindow = true,
        });
    }

    private void TryDelete(string path)
    {
        try { if (File.Exists(path)) File.Delete(path); }
        catch { /* best effort */ }
    }
}
