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
/// unaffected — the Tray still claims those itself.
///
/// Execution runs OFF the beat loop. It was originally awaited inline, which meant a device
/// installing Windows updates — tens of minutes of synchronous download and install — sent no
/// heartbeat for the whole run and was shown as offline three minutes in, while it was doing
/// exactly what it had been asked to do. Worse, the operator saw an idle-looking device and
/// pressed the button again.
///
/// One action still runs at a time; that part was right. It is enforced by not ASKING for work
/// while busy, rather than by blocking the loop — so the beat keeps going out, the device stays
/// visibly online, and the backend never marks a task dispatched that this agent cannot yet
/// start.</summary>
public sealed class HeartbeatWorker(
    IEnrollmentService enrollment,
    IAstraApiClient api,
    IDeviceIdentityProvider identity,
    ISystemTaskRunner taskRunner,
    IOptions<AgentOptions> options,
    ILogger<HeartbeatWorker> logger) : BackgroundService
{
    private static readonly TimeSpan MaxBackoff = TimeSpan.FromMinutes(15);

    // 1 while an action is executing. Read on the beat loop, cleared on the worker task.
    private int _executing;

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

        // Don't ask for work we can't start yet. Claiming marks a task dispatched on the
        // backend, so pulling one down while an action is already running would show it as
        // being executed when it is really sitting in this process waiting its turn.
        var busy = Volatile.Read(ref _executing) == 1;

        var request = new HeartbeatRequest(
            AgentVersion.Current,
            LoggedInUserResolver.GetConsoleUser(),
            IncludeTasks: !busy,
            OsVersion: _osVersion.Value,
            UsbStorageBlocked: Remediation.UsbStorageManager.IsBlocked());
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

        if (result.Tasks.Count > 0 && Interlocked.CompareExchange(ref _executing, 1, 0) == 0)
        {
            logger.LogInformation("Heartbeat returned {Count} system task(s)", result.Tasks.Count);
            var claimed = result.Tasks;
            var claimToken = token;
            // Deliberately not awaited: the beat must keep going while this runs. The flag is
            // cleared in the finally, so a throw here can never wedge the agent into a state
            // where it stops asking for work.
            _ = Task.Run(async () =>
            {
                try
                {
                    await taskRunner.RunAsync(claimToken, claimed, api, ct);
                }
                catch (OperationCanceledException) when (ct.IsCancellationRequested)
                {
                    // Service is stopping — the backend times the task out on its own.
                }
                catch (Exception ex)
                {
                    logger.LogError(ex, "System task execution failed");
                }
                finally
                {
                    Volatile.Write(ref _executing, 0);
                }
            }, ct);
        }

        return true;
    }
}
