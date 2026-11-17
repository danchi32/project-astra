using AstraAgent.Service;
using AstraAgent.Service.Api;
using AstraAgent.Service.Enrollment;
using AstraAgent.Service.Guard;
using AstraAgent.Service.Update;
using Microsoft.Extensions.Logging.Abstractions;
using Microsoft.Extensions.Options;
using Xunit;

namespace AstraAgent.Service.Tests;

/// <summary>
/// Phase 3 · D10 worker: fetch hourly, apply every cycle, report only when something
/// happened. Never remove the policy because the backend was unreachable. The writer is
/// replaced, so nothing here touches the registry.
/// </summary>
public class BrowserPolicyWorkerTests
{
    sealed class Enrollment : IEnrollmentService
    {
        public string Token = "tok-1";
        public Task<string?> GetDeviceTokenAsync(CancellationToken ct) => Task.FromResult<string?>(Token);
        public Task<string?> ReEnrollAsync(CancellationToken ct) => Task.FromResult<string?>(Token);
    }

    /// <summary>Only the two D10 calls matter; the rest of the interface is never reached.</summary>
    sealed class Api : IAstraApiClient
    {
        public AgentBrowserPolicy? Next;
        public int Fetches;
        public readonly List<(int Version, IReadOnlyList<ApplyReport> Reports)> Reports = [];

        public Task<AgentBrowserPolicy?> GetBrowserPolicyAsync(string t, CancellationToken ct) { Fetches++; return Task.FromResult(Next); }
        public Task<bool> ReportBrowserPolicyAsync(string t, int v, IReadOnlyList<ApplyReport> r, CancellationToken ct)
        { Reports.Add((v, r)); return Task.FromResult(true); }

        public Task<EnrollResponse?> EnrollAsync(EnrollRequest request, CancellationToken ct) => throw new NotSupportedException();
        public Task<HeartbeatResult> HeartbeatAsync(string token, HeartbeatRequest request, CancellationToken ct) => throw new NotSupportedException();
        public Task<bool> PushTelemetryAsync(string token, TelemetryPush payload, CancellationToken ct) => throw new NotSupportedException();
        public Task<bool> PushOfflineEventsAsync(string token, IReadOnlyList<AstraAgent.Service.Net.JournalEntry> entries, CancellationToken ct) => throw new NotSupportedException();
        public Task<bool> EscrowBitLockerKeysAsync(string t, IReadOnlyList<AstraAgent.Service.Telemetry.Collectors.BitLockerRecoveryKey> k, CancellationToken ct) => throw new NotSupportedException();
        public Task<UpdateEnvelope?> GetUpdateAsync(string token, CancellationToken ct) => throw new NotSupportedException();
        public Task<RemoteSupportPlan?> GetRemoteSupportPlanAsync(string token, CancellationToken ct) => throw new NotSupportedException();
        public Task<IReadOnlyList<AgentRemediationTask>?> ClaimTasksAsync(string token, string context, CancellationToken ct) => throw new NotSupportedException();
        public Task<bool> ReportTaskResultAsync(string token, Guid taskId, AgentRemediationResult result, CancellationToken ct) => throw new NotSupportedException();
    }

    static ApplyReport Report(Browser b, string[]? set = null, string[]? repaired = null, string[]? conflicts = null) =>
        new(b, set ?? [], repaired ?? [], [], conflicts ?? [], null);

    readonly Enrollment _enroll = new();
    readonly Api _api = new();
    readonly List<BrowserPolicy> _applied = [];
    Func<BrowserPolicy, IReadOnlyList<ApplyReport>> _result = _ => [Report(Browser.Chrome)];

    BrowserPolicyWorker Worker() => new(_enroll, _api, new SubscriptionState(),
        Options.Create(new AgentOptions()), NullLogger<BrowserPolicyWorker>.Instance)
    {
        Apply = p => { _applied.Add(p); return _result(p); },
    };

    static AgentBrowserPolicy Policy(int version, bool incognitoOff = true) =>
        new(version, new AgentBrowserPolicyBody(IncognitoOff: incognitoOff, BlockedSites: ["example.com"]));

    [Fact]
    public async Task Fetches_hourly_applies_every_cycle_reports_only_on_change()
    {
        var w = Worker();
        var t0 = new DateTime(2026, 11, 17, 9, 0, 0, DateTimeKind.Utc);
        _api.Next = Policy(3);
        _result = _ => [Report(Browser.Chrome, set: ["IncognitoModeAvailability"])];
        await w.RunOnceAsync(t0, default);
        Assert.Equal(1, _api.Fetches);
        Assert.True(_applied[0].IncognitoOff);
        Assert.Equal(["example.com"], _applied[0].BlockedSites);
        Assert.Equal(3, Assert.Single(_api.Reports).Version);

        _result = _ => [Report(Browser.Chrome)];                       // nothing to do now
        await w.RunOnceAsync(t0.AddMinutes(1), default);
        await w.RunOnceAsync(t0.AddMinutes(2), default);
        Assert.Equal(1, _api.Fetches);                                  // not before the hour
        Assert.Equal(3, _applied.Count);                                // but applied every cycle
        Assert.Single(_api.Reports);                                    // nothing changed: nothing to say

        _result = _ => [Report(Browser.Chrome, repaired: ["IncognitoModeAvailability"])];   // tampered
        await w.RunOnceAsync(t0.AddMinutes(3), default);
        Assert.Equal(2, _api.Reports.Count);
        Assert.Equal(["IncognitoModeAvailability"], _api.Reports[^1].Reports[0].Repaired);

        await w.RunOnceAsync(t0.AddHours(1).AddMinutes(1), default);
        Assert.Equal(2, _api.Fetches);
    }

    [Fact]
    public async Task An_unreachable_backend_never_removes_the_policy()
    {
        var w = Worker();
        var t0 = new DateTime(2026, 11, 17, 9, 0, 0, DateTimeKind.Utc);
        await w.RunOnceAsync(t0, default);                              // never heard from the backend
        Assert.Empty(_applied);

        _api.Next = Policy(2);
        await w.RunOnceAsync(t0.AddMinutes(5), default);                 // retried after 5 minutes
        Assert.True(_applied[^1].IncognitoOff);

        _api.Next = null;                                                // backend down from now on
        await w.RunOnceAsync(t0.AddHours(2), default);
        Assert.True(_applied[^1].IncognitoOff);                          // still the last policy
    }

    [Fact]
    public async Task An_empty_policy_from_the_backend_removes_what_savio_set()
    {
        var w = Worker();
        var t0 = new DateTime(2026, 11, 17, 9, 0, 0, DateTimeKind.Utc);
        _api.Next = Policy(4);
        await w.RunOnceAsync(t0, default);
        _api.Next = new AgentBrowserPolicy(0, new AgentBrowserPolicyBody());   // AI Guard turned off
        await w.RunOnceAsync(t0.AddHours(1), default);
        var last = _applied[^1];
        Assert.False(last.IncognitoOff);
        Assert.Empty(last.BlockedSites);
        Assert.Equal(0, _api.Reports[^1].Version);
    }

    [Fact]
    public async Task A_re_enrolled_device_fetches_and_reports_afresh()
    {
        var w = Worker();
        var t0 = new DateTime(2026, 11, 17, 9, 0, 0, DateTimeKind.Utc);
        _api.Next = Policy(1);
        await w.RunOnceAsync(t0, default);
        _enroll.Token = "tok-2";
        await w.RunOnceAsync(t0.AddMinutes(1), default);
        Assert.Equal(2, _api.Fetches);
        Assert.Equal(2, _api.Reports.Count);
    }
}
