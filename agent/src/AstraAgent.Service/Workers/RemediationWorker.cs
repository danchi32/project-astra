using AstraAgent.Service.Api;
using AstraAgent.Service.Enrollment;
using AstraAgent.Service.Remediation;
using Microsoft.Extensions.Options;

namespace AstraAgent.Service.Workers;

/// <summary>Polls for approved *system-context* remediation tasks (the elevated cleanup the
/// user-session Tray can't do), executes each via the allowlisted SystemRemediationExecutor,
/// and reports the result. The user-context Tray claims context="user"; this worker claims
/// context="system", so the two never take each other's tasks.</summary>
public sealed class RemediationWorker(
    IEnrollmentService enrollment,
    IAstraApiClient api,
    IOptions<AgentOptions> options,
    ILogger<RemediationWorker> logger) : BackgroundService
{
    private const string Context = "system";
    // Hard ceiling for a single system action (a Windows Update install can run for minutes);
    // beyond this the loop stops waiting so a wedged call can't disable system remediation.
    private static readonly TimeSpan MaxExecution = TimeSpan.FromMinutes(60);
    private readonly SystemRemediationExecutor _executor = new();

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        var interval = TimeSpan.FromSeconds(Math.Max(10, options.Value.RemediationPollSeconds));

        while (!stoppingToken.IsCancellationRequested)
        {
            try
            {
                await PollOnceAsync(stoppingToken);
            }
            catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested)
            {
                break;
            }
            catch (Exception ex)
            {
                logger.LogError(ex, "Remediation poll cycle failed");
            }

            try { await Task.Delay(interval, stoppingToken); }
            catch (OperationCanceledException) { break; }
        }
    }

    private async Task PollOnceAsync(CancellationToken ct)
    {
        var token = await enrollment.GetDeviceTokenAsync(ct);
        if (token is null)
            return;   // not enrolled yet

        var tasks = await api.ClaimTasksAsync(token, Context, ct);
        if (tasks is null)
        {
            // Credential rotated / device decommissioned — one re-enroll attempt, then retry next cycle.
            logger.LogWarning("Task claim unauthorized; attempting re-enrollment");
            token = await enrollment.ReEnrollAsync(ct);
            if (token is null)
                return;
            tasks = await api.ClaimTasksAsync(token, Context, ct);
        }

        if (tasks is null || tasks.Count == 0)
            return;

        foreach (var task in tasks)
        {
            // Independent allowlist: refuse anything this executor doesn't explicitly support,
            // even if the backend somehow dispatched it here.
            bool success;
            string output;
            if (!SystemRemediationExecutor.SupportedActions.Contains(task.ActionId))
            {
                success = false;
                output = $"Action '{task.ActionId}' is not permitted in the elevated service.";
                logger.LogWarning("Refused non-allowlisted system action {ActionId}", task.ActionId);
            }
            else
            {
                logger.LogInformation("Executing system remediation {ActionId}", task.ActionId);
                // Run on a worker thread with a hard time budget: a Windows Update install can
                // legitimately take minutes, but a wedged WUA call must never permanently block
                // this poll loop (which would silently disable all system remediation here).
                var execTask = Task.Run(() => _executor.Execute(task.ActionId, task.Params), ct);
                if (await Task.WhenAny(execTask, Task.Delay(MaxExecution, ct)) == execTask)
                {
                    (success, output) = await execTask;
                }
                else
                {
                    success = false;
                    output = $"Action timed out after {MaxExecution.TotalMinutes:0} minutes; it may "
                           + "still be completing in the background. Check the device.";
                }
                logger.LogInformation("System remediation {ActionId} -> success={Success}",
                    task.ActionId, success);
            }

            // Report each result independently: a transient failure reporting one task must
            // not abandon the results of the others already executed in this batch.
            try
            {
                await api.ReportTaskResultAsync(
                    token, task.Id, new AgentRemediationResult(success, output), ct);
            }
            catch (Exception ex) when (ex is not OperationCanceledException)
            {
                logger.LogWarning(ex, "Failed to report result for task {TaskId}", task.Id);
            }
        }
    }
}
