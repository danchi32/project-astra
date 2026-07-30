using AstraAgent.Service.Api;
using AstraAgent.Service.Enrollment;
using AstraAgent.Service.Remediation;
using Microsoft.Extensions.Options;

namespace AstraAgent.Service.Workers;

/// <summary>Reports liveness every interval, and executes any system-context remediation the
/// backend hands back on the same call.
///
/// Task delivery used to be a separate 30s poll (RemediationWorker) that almost always
/// returned nothing — roughly a fifth of all traffic this agent generated, on a device that
/// was already calling home every 60s anyway. Folding it into the beat removes those requests
/// entirely rather than making them cheaper.
///
/// The cost is latency: a system fix now arrives within one heartbeat (60s) instead of 30s.
/// That is an acceptable trade for elevated actions like cleaning C:\Windows\Temp or resetting
/// the network stack, which take longer to run than to arrive. User-context fixes are
/// unaffected — the Tray still claims those itself.</summary>
public sealed class HeartbeatWorker(
    IEnrollmentService enrollment,
    IAstraApiClient api,
    IDeviceIdentityProvider identity,
    SystemTaskRunner taskRunner,
    IOptions<AgentOptions> options,
    ILogger<HeartbeatWorker> logger) : BackgroundService
{
    private static readonly TimeSpan MaxBackoff = TimeSpan.FromMinutes(15);

    // Resolved once per process, not per beat: reading it costs a WMI query, and the OS name
    // can only change across a reboot — which restarts this service anyway.
    private readonly Lazy<string?> _osVersion = new(() =>
    {
        try { return identity.Collect().OsVersion; }
        catch { return null; }   // never let naming the OS stop the device reporting in
    });

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        var interval = TimeSpan.FromSeconds(options.Value.HeartbeatIntervalSeconds);
        var failures = 0;

        while (!stoppingToken.IsCancellationRequested)
        {
            try
            {
                failures = await BeatOnceAsync(stoppingToken) ? 0 : failures + 1;
            }
            catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested)
            {
                break;
            }
            catch (Exception ex)
            {
                failures++;
                logger.LogError(ex, "Heartbeat cycle failed");
            }

            try
            {
                await Task.Delay(BackoffCalculator.NextDelay(failures, interval, MaxBackoff), stoppingToken);
            }
            catch (OperationCanceledException)
            {
                break;
            }
        }
    }

    private async Task<bool> BeatOnceAsync(CancellationToken ct)
    {
        var token = await enrollment.GetDeviceTokenAsync(ct);
        if (token is null)
            return false;

        var request = new HeartbeatRequest(
            AgentVersion.Current,
            LoggedInUserResolver.GetConsoleUser(),
            OsVersion: _osVersion.Value);
        var result = await api.HeartbeatAsync(token, request, ct);

        if (result.Status == HeartbeatStatus.Unauthorized)
        {
            // Credential was rotated or the device was decommissioned; one re-enroll attempt.
            logger.LogWarning("Device credential rejected; attempting re-enrollment");
            token = await enrollment.ReEnrollAsync(ct);
            if (token is null)
                return false;
            result = await api.HeartbeatAsync(token, request, ct);
        }

        if (result.Status != HeartbeatStatus.Ok)
            return false;

        // Execution is awaited inline: the next beat is 60s away, and running tasks
        // sequentially keeps two long actions from overlapping on the same machine. A wedged
        // action can't stall the loop indefinitely — SystemTaskRunner caps each one.
        if (result.Tasks.Count > 0)
        {
            logger.LogInformation("Heartbeat returned {Count} system task(s)", result.Tasks.Count);
            await taskRunner.RunAsync(token, result.Tasks, api, ct);
        }

        return true;
    }
}
