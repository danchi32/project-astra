using AstraAgent.Service.Api;

namespace AstraAgent.Service.Remediation;

/// <summary>Executes approved system-context remediation tasks and reports each result.
///
/// Extracted from the old RemediationWorker when task delivery moved onto the heartbeat.
/// It lives on its own rather than inside the worker so the safety rules below exist in
/// exactly one place — duplicating them into a second caller is how one copy quietly drifts
/// and stops enforcing the allowlist.</summary>
public interface ISystemTaskRunner
{
    Task RunAsync(
        string deviceToken,
        IReadOnlyList<AgentRemediationTask> tasks,
        IAstraApiClient api,
        CancellationToken ct);
}

public sealed class SystemTaskRunner(ILogger<SystemTaskRunner> logger) : ISystemTaskRunner
{
    // Hard ceiling for a single action. A Windows Update install can legitimately run for
    // minutes, but a wedged WUA call must never block the caller forever — that would
    // silently disable system remediation on the device.
    private static readonly TimeSpan MaxExecution = TimeSpan.FromMinutes(60);

    private readonly SystemRemediationExecutor _executor = new();

    public async Task RunAsync(
        string deviceToken,
        IReadOnlyList<AgentRemediationTask> tasks,
        IAstraApiClient api,
        CancellationToken ct)
    {
        foreach (var task in tasks)
        {
            bool success;
            string output;

            // Independent allowlist. The backend already decides what may run where, but this
            // process holds SYSTEM privileges, so it refuses anything it doesn't itself
            // recognise rather than trusting what it was handed.
            if (!SystemRemediationExecutor.SupportedActions.Contains(task.ActionId))
            {
                success = false;
                output = $"Action '{task.ActionId}' is not permitted in the elevated service.";
                logger.LogWarning("Refused non-allowlisted system action {ActionId}", task.ActionId);
            }
            else
            {
                logger.LogInformation("Executing system remediation {ActionId}", task.ActionId);
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

            // Report each result independently: failing to report one must not abandon the
            // results of tasks already executed alongside it.
            try
            {
                await api.ReportTaskResultAsync(
                    deviceToken, task.Id, new AgentRemediationResult(success, output), ct);
            }
            catch (Exception ex) when (ex is not OperationCanceledException)
            {
                logger.LogWarning(ex, "Failed to report result for task {TaskId}", task.Id);
            }
        }
    }
}
