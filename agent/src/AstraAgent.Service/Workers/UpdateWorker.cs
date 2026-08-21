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

        // The floor records versions this device has actually RUN — and this is the only place an
        // agent version ever enters it. Recording what is running keeps the rollback protection
        // (a replayed older manifest still loses to it) while making it impossible for the floor
        // to outrun reality and block a genuine update. See CheckOnceAsync for why that matters.
        _floor.Raise(AgentVersion.Current);

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

        // Anti-replay floor: the version we're running and any signed min_version raise a
        // monotonic floor. Refuse anything at or below it so a replayed older-but-signed manifest
        // can't roll the agent back.
        //
        // Nothing may raise the floor TO the offered version before the check below — that makes
        // the floor equal to the offer, strictly-newer can never be satisfied, and the agent
        // refuses its own update forever. So a signed min_version is persisted only when it sits
        // strictly below what's on offer. A manifest that sets min_version to its own version (the
        // natural way to say "everyone must be at least here") still works: installing it raises
        // the floor to exactly that version on the next start, via ExecuteAsync.
        if (UpdatePolicy.ShouldPersistMinVersion(manifest.Version, manifest.MinVersion))
            _floor.Raise(manifest.MinVersion!);

        if (!UpdatePolicy.IsApplicable(AgentVersion.Current, manifest.Version, _floor.Current()))
        {
            // Newer than we run but not above the floor ⇒ a superseded/replayed manifest.
            if (SemVer.IsNewer(manifest.Version, AgentVersion.Current))
                logger.LogWarning(
                    "Refusing update {New}: below the version floor {Floor} (possible rollback/replay).",
                    manifest.Version, _floor.Current());
            return false;
        }

        logger.LogInformation(
            "Newer agent {New} available (running {Cur}); applying.",
            manifest.Version, AgentVersion.Current);

        // The floor is deliberately NOT raised to manifest.Version here: an offer is not an
        // install. ApplyAsync can fail (download, hash, DACL, malformed package), and the apply
        // script it hands off to can fail after that. Recording the offered version would leave
        // the floor EQUAL to the version still being offered — and IsApplicable requires strictly
        // newer — so the device would refuse that update forever and sit on the old build until a
        // higher version shipped. Only versions we have actually run raise the floor (ExecuteAsync).
        return await installer.ApplyAsync(manifest, lifetime, ct);
    }

}
