using AstraAgent.Service.Api;
using AstraAgent.Service.Enrollment;
using Microsoft.Extensions.Options;

namespace AstraAgent.Service.Workers;

public sealed class HeartbeatWorker(
    IEnrollmentService enrollment,
    IAstraApiClient api,
    IOptions<AgentOptions> options,
    ILogger<HeartbeatWorker> logger) : BackgroundService
{
    private static readonly TimeSpan MaxBackoff = TimeSpan.FromMinutes(15);

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

        var request = new HeartbeatRequest(AgentVersion.Current, LoggedInUserResolver.GetConsoleUser());
        var status = await api.HeartbeatAsync(token, request, ct);

        if (status == HeartbeatStatus.Unauthorized)
        {
            // Credential was rotated or the device was decommissioned; one re-enroll attempt.
            logger.LogWarning("Device credential rejected; attempting re-enrollment");
            token = await enrollment.ReEnrollAsync(ct);
            if (token is null)
                return false;
            status = await api.HeartbeatAsync(token, request, ct);
        }

        return status == HeartbeatStatus.Ok;
    }
}
