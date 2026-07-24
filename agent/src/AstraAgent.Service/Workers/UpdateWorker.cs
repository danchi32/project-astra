using AstraAgent.Service.Api;
using AstraAgent.Service.Enrollment;
using AstraAgent.Service.Update;
using Microsoft.Extensions.Options;

namespace AstraAgent.Service.Workers;

/// <summary>Periodically asks the backend for a newer signed release and, when one verifies
/// against the pinned public key, applies it. If no real signing key is pinned into this build
/// the worker does nothing at all — auto-update is opt-in via the embedded key.</summary>
public sealed class UpdateWorker(
    IEnrollmentService enrollment,
    IAstraApiClient api,
    UpdateInstaller installer,
    IHostApplicationLifetime lifetime,
    IOptions<AgentOptions> options,
    ILogger<UpdateWorker> logger) : BackgroundService
{
    private readonly UpdateVerifier? _verifier = UpdateVerifier.FromEmbeddedKey();
    private readonly UpdateFloorStore _floor = new();

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        if (_verifier is null)
        {
            logger.LogInformation(
                "Auto-update disabled: no update-signing key is pinned into this build.");
            return;
        }

        var interval = TimeSpan.FromMinutes(Math.Max(5, options.Value.UpdateCheckIntervalMinutes));

        // Give enrollment a moment to settle before the first check.
        try { await Task.Delay(TimeSpan.FromMinutes(2), stoppingToken); }
        catch (OperationCanceledException) { return; }

        while (!stoppingToken.IsCancellationRequested)
        {
            try
            {
                if (await CheckOnceAsync(stoppingToken))
                    return;   // an update is being applied; the host is shutting down
            }
            catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested)
            {
                return;
            }
            catch (Exception ex)
            {
                logger.LogError(ex, "Update check failed");
            }

            try { await Task.Delay(interval, stoppingToken); }
            catch (OperationCanceledException) { return; }
        }
    }

    /// <summary>Returns true when an update has been staged and shutdown requested.</summary>
    private async Task<bool> CheckOnceAsync(CancellationToken ct)
    {
        var token = await enrollment.GetDeviceTokenAsync(ct);
        if (token is null)
            return false;

        var envelope = await api.GetUpdateAsync(token, ct);
        if (envelope is null || !envelope.Available
            || string.IsNullOrEmpty(envelope.Manifest) || string.IsNullOrEmpty(envelope.Signature))
            return false;

        var manifest = _verifier!.Verify(envelope.Manifest, envelope.Signature);
        if (manifest is null)
        {
            // A served manifest that doesn't verify is a red flag — never act on it.
            logger.LogWarning("Ignoring an update manifest that failed signature verification.");
            return false;
        }

        // Anti-replay floor: the highest version we've applied before, the version we're running,
        // and any signed min_version raise a monotonic floor. Refuse anything at or below it so a
        // replayed older-but-signed manifest can't roll the agent back.
        //
        // The manifest's OWN version must NOT raise the floor before this check — doing so makes
        // the floor equal to the offered version, so the agent would refuse its own update. We
        // record it only once we've decided to apply (below).
        if (!string.IsNullOrEmpty(manifest.MinVersion))
            _floor.Raise(manifest.MinVersion!);

        if (!IsApplicable(AgentVersion.Current, manifest.Version, _floor.Current()))
        {
            // Newer than we run but not above the floor ⇒ a superseded/replayed manifest.
            if (SemVer.IsNewer(manifest.Version, AgentVersion.Current))
                logger.LogWarning(
                    "Refusing update {New}: below the version floor {Floor} (possible rollback/replay).",
                    manifest.Version, _floor.Current());
            return false;
        }

        // Decided to apply — now record this version so a later replay of an older signed manifest
        // is refused even before the new build is running.
        _floor.Raise(manifest.Version);

        logger.LogInformation(
            "Newer agent {New} available (running {Cur}); applying.",
            manifest.Version, AgentVersion.Current);
        return await installer.ApplyAsync(manifest, lifetime, ct);
    }

    /// <summary>Pure decision: may we apply <paramref name="manifestVersion"/> given the running
    /// version and the current anti-replay floor? The offered version must be strictly newer than
    /// both. Crucially, <paramref name="floorNow"/> must NOT already include the offered version —
    /// otherwise the agent refuses its own update (the bug this replaced).</summary>
    internal static bool IsApplicable(string currentVersion, string manifestVersion, string floorNow)
    {
        var floor = floorNow;
        if (SemVer.Compare(currentVersion, floor) > 0)
            floor = currentVersion;
        return SemVer.IsNewer(manifestVersion, floor);
    }
}
