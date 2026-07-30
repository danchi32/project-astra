using AstraAgent.Service;
using AstraAgent.Service.Api;
using AstraAgent.Service.Enrollment;
using AstraAgent.Service.Remediation;
using AstraAgent.Service.Update;
using AstraAgent.Service.Workers;
using Microsoft.Extensions.Logging.Abstractions;
using Microsoft.Extensions.Options;
using Xunit;

namespace AstraAgent.Service.Tests;

/// <summary>The beat must keep going while an action runs.
///
/// Execution used to be awaited on the beat loop, so a device installing Windows updates —
/// tens of minutes of synchronous work — sent no heartbeat at all for the duration and was
/// marked offline after three minutes while doing exactly what it had been asked to do.
/// Nothing failed loudly; the device simply looked dead, which is why this went out in a
/// release and was found on a live machine rather than here.</summary>
public class HeartbeatWorkerTests
{
    private sealed class FakeEnrollment : IEnrollmentService
    {
        public Task<string?> GetDeviceTokenAsync(CancellationToken ct) => Task.FromResult<string?>("device-token");
        public Task<string?> ReEnrollAsync(CancellationToken ct) => Task.FromResult<string?>("device-token");
    }

    private sealed class FakeIdentity : IDeviceIdentityProvider
    {
        public DeviceIdentity Collect() => new("HOST", "machine-guid", "Windows 11 Pro 25H2 (build 26200)", null);
    }

    private sealed class CountingApi : IAstraApiClient
    {
        private int _beats;
        public int Beats => Volatile.Read(ref _beats);
        public IReadOnlyList<AgentRemediationTask> NextTasks { get; set; } = [];
        public readonly List<bool> IncludeTasksSeen = [];

        public Task<HeartbeatResult> HeartbeatAsync(string token, HeartbeatRequest request, CancellationToken ct)
        {
            Interlocked.Increment(ref _beats);
            lock (IncludeTasksSeen) IncludeTasksSeen.Add(request.IncludeTasks);
            var tasks = request.IncludeTasks ? NextTasks : [];
            NextTasks = [];   // hand each task out once, as the backend does
            return Task.FromResult(new HeartbeatResult(HeartbeatStatus.Ok, tasks));
        }

        public Task<EnrollResponse?> EnrollAsync(EnrollRequest request, CancellationToken ct)
            => Task.FromResult<EnrollResponse?>(null);
        public Task<bool> PushTelemetryAsync(string token, TelemetryPush payload, CancellationToken ct)
            => Task.FromResult(true);
        public Task<UpdateEnvelope?> GetUpdateAsync(string token, CancellationToken ct)
            => Task.FromResult<UpdateEnvelope?>(null);
        public Task<IReadOnlyList<AgentRemediationTask>?> ClaimTasksAsync(string token, string context, CancellationToken ct)
            => Task.FromResult<IReadOnlyList<AgentRemediationTask>?>([]);
        public Task<bool> ReportTaskResultAsync(string token, Guid taskId, AgentRemediationResult result, CancellationToken ct)
            => Task.FromResult(true);
    }

    /// <summary>A task runner that never finishes on its own — stands in for a long Windows
    /// Update install without waiting minutes for one.</summary>
    private sealed class BlockingRunner : ISystemTaskRunner
    {
        public readonly TaskCompletionSource Started = new(TaskCreationOptions.RunContinuationsAsynchronously);
        public readonly TaskCompletionSource Release = new(TaskCreationOptions.RunContinuationsAsynchronously);

        public async Task RunAsync(string deviceToken, IReadOnlyList<AgentRemediationTask> tasks,
                                   IAstraApiClient api, CancellationToken ct)
        {
            Started.TrySetResult();
            await Release.Task;
        }
    }

    private static HeartbeatWorker Build(CountingApi api, ISystemTaskRunner runner)
    {
        var options = Options.Create(new AgentOptions { HeartbeatIntervalSeconds = 1 });
        return new HeartbeatWorker(
            new FakeEnrollment(), api, new FakeIdentity(), runner, options,
            NullLogger<HeartbeatWorker>.Instance);
    }

    [Fact]
    public async Task Heartbeats_continue_while_a_long_action_is_running()
    {
        var api = new CountingApi
        {
            NextTasks = [new AgentRemediationTask(Guid.NewGuid(), "windows_update_install", null)],
        };
        var runner = new BlockingRunner();
        var worker = Build(api, runner);

        using var cts = new CancellationTokenSource();
        await worker.StartAsync(cts.Token);
        try
        {
            await runner.Started.Task.WaitAsync(TimeSpan.FromSeconds(10));
            var atStart = api.Beats;

            // The action is still running and will not finish. Beats must keep going anyway.
            await Task.Delay(TimeSpan.FromSeconds(3), cts.Token);

            Assert.True(api.Beats > atStart,
                $"heartbeats stopped while an action ran ({atStart} before, {api.Beats} after)");
        }
        finally
        {
            runner.Release.TrySetResult();
            cts.Cancel();
            await worker.StopAsync(CancellationToken.None);
        }
    }

    [Fact]
    public async Task No_new_work_is_claimed_while_an_action_is_running()
    {
        // One action at a time was always the intent. It is now enforced by not asking for
        // work rather than by blocking the loop: claiming marks a task dispatched on the
        // backend, so pulling one down that this process cannot start yet would report it as
        // executing while it sat in a queue here.
        var api = new CountingApi
        {
            NextTasks = [new AgentRemediationTask(Guid.NewGuid(), "clear_system_temp", null)],
        };
        var runner = new BlockingRunner();
        var worker = Build(api, runner);

        using var cts = new CancellationTokenSource();
        await worker.StartAsync(cts.Token);
        try
        {
            await runner.Started.Task.WaitAsync(TimeSpan.FromSeconds(10));
            await Task.Delay(TimeSpan.FromSeconds(3), cts.Token);

            List<bool> seen;
            lock (api.IncludeTasksSeen) seen = [.. api.IncludeTasksSeen];

            // Assert there ARE later beats before asserting what they contain. Without this
            // the test passes against the very code it exists to reject: the old inline await
            // produced no further beats at all, so "none of the later beats asked for work"
            // was vacuously true.
            Assert.True(seen.Count > 1, $"expected beats to continue during the action, saw {seen.Count}");
            Assert.True(seen[0], "the first beat should ask for work");
            Assert.All(seen.Skip(1), asked => Assert.False(asked));
        }
        finally
        {
            runner.Release.TrySetResult();
            cts.Cancel();
            await worker.StopAsync(CancellationToken.None);
        }
    }
}
