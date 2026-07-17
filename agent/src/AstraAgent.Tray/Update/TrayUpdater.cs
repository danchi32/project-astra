using System;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Threading;
using System.Threading.Tasks;
using AstraAgent.Service;
using AstraAgent.Service.Security;
using AstraAgent.Service.Update;

namespace AstraAgent.Tray.Update;

/// <summary>Self-updates the tray in the user's session: polls the backend for a newer signed
/// release, verifies it against the pinned public key (shared with the service) plus the SHA-256
/// of the download, then swaps its own files in the user-writable live dir and relaunches.
///
/// Runs only when the tray is executing from its live copy (so it can write its own files) and a
/// real signing key is pinned — otherwise it does nothing, exactly like the service updater.</summary>
public sealed class TrayUpdater : IDisposable
{
    private readonly HttpClient _http;
    private readonly ITokenStore _store;
    private readonly UpdateVerifier? _verifier = UpdateVerifier.FromEmbeddedKey();
    private readonly UpdateFloorStore _floor = new(Path.Combine(TrayPaths.UpdateWorkDir, "version-floor.txt"));
    private readonly CancellationTokenSource _cts = new();

    public TrayUpdater(string serverUrl, ITokenStore store)
    {
        _http = new HttpClient { BaseAddress = new Uri(serverUrl), Timeout = TimeSpan.FromSeconds(30) };
        _store = store;
    }

    public void Start()
    {
        // Disabled unless we can write our own files AND a real key is pinned (fail-safe).
        if (_verifier is null || !TrayPaths.RunningFromLiveDir())
            return;
        try { Directory.CreateDirectory(TrayPaths.UpdateWorkDir); } catch { /* floor persistence is best-effort */ }
        _ = RunAsync(_cts.Token);
    }

    private async Task RunAsync(CancellationToken ct)
    {
        try { await Task.Delay(TimeSpan.FromMinutes(2), ct); }
        catch (OperationCanceledException) { return; }

        while (!ct.IsCancellationRequested)
        {
            try
            {
                if (await CheckOnceAsync(ct))
                    return;   // applying — the process is exiting
            }
            catch (OperationCanceledException) { return; }
            catch { /* transient — retry next cycle */ }

            try { await Task.Delay(TimeSpan.FromMinutes(60), ct); }
            catch (OperationCanceledException) { return; }
        }
    }

    private async Task<bool> CheckOnceAsync(CancellationToken ct)
    {
        var token = _store.Load();
        if (token is null)
            return false;

        using var request = new HttpRequestMessage(HttpMethod.Get, "/api/v1/agent/update");
        request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", token);
        UpdateEnvelope? envelope;
        try
        {
            using var response = await _http.SendAsync(request, ct);
            if (!response.IsSuccessStatusCode)
                return false;
            envelope = await response.Content.ReadFromJsonAsync<UpdateEnvelope>(ct);
        }
        catch (Exception ex) when (ex is HttpRequestException or TaskCanceledException)
        {
            return false;
        }

        if (envelope is null || !envelope.Available
            || string.IsNullOrEmpty(envelope.Manifest) || string.IsNullOrEmpty(envelope.Signature))
            return false;

        var manifest = _verifier!.Verify(envelope.Manifest, envelope.Signature);
        if (manifest is null)
            return false;

        // Same monotonic anti-replay floor as the service updater.
        _floor.Raise(manifest.Version);
        if (!string.IsNullOrEmpty(manifest.MinVersion))
            _floor.Raise(manifest.MinVersion!);
        var floor = _floor.Current();
        if (SemVer.Compare(AgentVersion.Current, floor) > 0)
            floor = AgentVersion.Current;
        if (!SemVer.IsNewer(manifest.Version, floor))
            return false;

        return await ApplyAsync(manifest, ct);
    }

    private async Task<bool> ApplyAsync(UpdateManifest manifest, CancellationToken ct)
    {
        var work = TrayPaths.UpdateWorkDir;
        var zipPath = Path.Combine(work, "pkg.zip");
        var staging = Path.Combine(work, "staging", manifest.Version);
        try
        {
            Directory.CreateDirectory(work);

            if (!await DownloadAsync(manifest.Url, zipPath, ct))
                return false;
            if (!UpdateVerifier.FileMatchesHash(zipPath, manifest.Sha256))
                return false;

            if (Directory.Exists(staging))
                Directory.Delete(staging, recursive: true);
            Directory.CreateDirectory(staging);
            ZipFile.ExtractToDirectory(zipPath, staging);

            // The combined package carries the tray under tray\; make sure it's really there.
            var trayPayload = Path.Combine(staging, "tray");
            if (!File.Exists(Path.Combine(trayPayload, "AstraAgent.Tray.dll")))
                return false;

            LaunchApplyScript(trayPayload, work, zipPath, manifest.Version);
            // Exit now so the script (which waits on our PID) can swap our locked files. Called
            // from this background task, so terminate the process directly rather than marshalling
            // Application.Exit to the UI thread; the script relaunches a fresh tray immediately.
            Environment.Exit(0);
            return true;
        }
        catch
        {
            return false;
        }
    }

    private async Task<bool> DownloadAsync(string url, string destPath, CancellationToken ct)
    {
        try
        {
            using var client = new HttpClient { Timeout = TimeSpan.FromMinutes(10) };
            using var response = await client.GetAsync(url, HttpCompletionOption.ResponseHeadersRead, ct);
            if (!response.IsSuccessStatusCode)
                return false;
            await using var src = await response.Content.ReadAsStreamAsync(ct);
            await using var dst = File.Create(destPath);
            await src.CopyToAsync(dst, ct);
            return true;
        }
        catch
        {
            return false;
        }
    }

    private void LaunchApplyScript(string trayPayload, string workDir, string zipPath, string version)
    {
        var pid = Environment.ProcessId;
        var host = Environment.ProcessPath ?? "dotnet";
        var liveDir = TrayPaths.LiveDir.TrimEnd('\\');
        var liveDll = Path.Combine(liveDir, "AstraAgent.Tray.dll");
        var scriptPath = Path.Combine(workDir, "apply-tray.cmd");

        // Wait for this tray to exit (PID match, not image name — the host is dotnet.exe), mirror
        // the new tray files in while keeping local config, record the version, relaunch the tray
        // in this same user session, then clean up. cwd is the live dir so the script isn't the
        // one holding the scratch dir open when it deletes it.
        var script = $"""
            @echo off
            setlocal
            :wait
            tasklist /FI "PID eq {pid}" /NH /FO CSV 2>nul | findstr /C:"\"{pid}\"" >nul
            if not errorlevel 1 (
                timeout /t 1 /nobreak >nul
                goto wait
            )
            robocopy "{trayPayload}" "{liveDir}" /E /R:3 /W:2 /XF "appsettings.json" >nul
            > "{TrayPaths.VersionMarker}" echo {version}
            start "" "{host}" "{liveDll}"
            rmdir /S /Q "{Path.Combine(workDir, "staging")}" >nul 2>&1
            del /Q "{zipPath}" >nul 2>&1
            del "%~f0" >nul 2>&1
            """;
        File.WriteAllText(scriptPath, script);

        Process.Start(new ProcessStartInfo
        {
            FileName = "cmd.exe",
            Arguments = $"/c \"{scriptPath}\"",
            WorkingDirectory = liveDir,
            UseShellExecute = false,
            CreateNoWindow = true,
        });
    }

    public void Dispose()
    {
        try { _cts.Cancel(); } catch { }
        _cts.Dispose();
        _http.Dispose();
    }
}
