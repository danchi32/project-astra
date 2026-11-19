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
    internal sealed class Enrollment : IEnrollmentService
    {
        public string? Token = "tok-1";
        public Task<string?> GetDeviceTokenAsync(CancellationToken ct) => Task.FromResult(Token);
        public Task<string?> ReEnrollAsync(CancellationToken ct) => Task.FromResult(Token);
    }

    /// <summary>Only the AI Guard calls matter; the rest of the interface is never reached.
    /// Shared with <see cref="GuardEventTests"/>.</summary>
    internal sealed class Api : IAstraApiClient
    {
        public AgentBrowserPolicy? Next;
        public int Fetches;
        public readonly List<(int Version, IReadOnlyList<ApplyReport> Reports)> Reports = [];
        public readonly List<IReadOnlyDictionary<string, int>> Closed = [];
        public bool ReportAccepted = true;
        public readonly List<IReadOnlyList<QueuedGuardEvent>> EventBatches = [];
        public bool EventsAccepted = true;

        public Task<AgentBrowserPolicy?> GetBrowserPolicyAsync(string t, CancellationToken ct) { Fetches++; return Task.FromResult(Next); }
        public readonly List<IReadOnlyList<SeenDrive>> Drives = [];
        public Task<bool> ReportBrowserPolicyAsync(string t, int v, IReadOnlyList<ApplyReport> r,
                                                   IReadOnlyDictionary<string, int> closed, IReadOnlyList<SeenDrive> drives,
                                                   CancellationToken ct)
        { Reports.Add((v, r)); Closed.Add(closed); Drives.Add(drives); return Task.FromResult(ReportAccepted); }
        public Task<bool> SendGuardEventsAsync(string t, IReadOnlyList<QueuedGuardEvent> events, CancellationToken ct)
        { EventBatches.Add(events); return Task.FromResult(EventsAccepted); }
        public IReadOnlyList<AgentGuardApproval>? Approvals = [];
        public int ApprovalFetches;
        public Task<IReadOnlyList<AgentGuardApproval>?> GetGuardApprovalsAsync(string t, CancellationToken ct)
        { ApprovalFetches++; return Task.FromResult(Approvals); }
        public readonly List<DiscoveryReport> Discoveries = [];
        public bool DiscoveryAccepted = true;
        public Task<bool> SendDiscoveryAsync(string t, DateTime at, DiscoveryReport r, CancellationToken ct)
        { Discoveries.Add(r); return Task.FromResult(DiscoveryAccepted); }
        public AgentUsbWindow? UsbWindow = new(null);
        public int UsbWindowFetches;
        public Task<AgentUsbWindow?> GetUsbWindowAsync(string t, CancellationToken ct)
        { UsbWindowFetches++; return Task.FromResult(UsbWindow); }
        public readonly List<(string User, string Reason)> UsbRequests = [];
        public int UsbRequestStatus = 202;
        public Task<int> RequestUsbWriteAsync(string t, string user, string reason, CancellationToken ct)
        { UsbRequests.Add((user, reason)); return Task.FromResult(UsbRequestStatus); }

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

    readonly List<IReadOnlyList<AgentGuardApproval>> _stored = [];

    IReadOnlyList<SeenDrive> _drives = [];

    BrowserPolicyWorker Worker() => new(_enroll, _api, new SubscriptionState(),
        Options.Create(new AgentOptions()), NullLogger<BrowserPolicyWorker>.Instance)
    {
        Apply = p => { _applied.Add(p); return _result(p); },
        StoreApprovals = a => _stored.Add(a),
        Drives = () => _drives,
    };

    [Fact]
    public async Task Drives_seen_are_reported_when_they_change_and_only_while_ai_guard_is_on()
    {
        var w = Worker();
        var t0 = new DateTime(2026, 11, 19, 9, 0, 0, DateTimeKind.Utc);
        _drives = [new(@"USBSTOR\Disk&Ven_SanDisk&Prod_Cruzer&Rev_1.00\4C530001&0", "SanDisk Cruzer", true)];
        _api.Next = Policy(1);
        await w.RunOnceAsync(t0, default);
        Assert.Equal("SanDisk Cruzer", Assert.Single(_api.Drives[^1]).Name);
        await w.RunOnceAsync(t0.AddMinutes(1), default);
        Assert.Single(_api.Reports);                                      // nothing new: nothing said
        _drives = [.. _drives, new(@"USBSTOR\Disk&Ven_General&Prod_USB_Disk&Rev_2.00\7&1a2b3c&0", "General USB Disk", false)];
        await w.RunOnceAsync(t0.AddMinutes(2), default);
        Assert.Equal(2, _api.Drives[^1].Count);                           // a new drive: reported

        _api.Next = new AgentBrowserPolicy(0, new AgentBrowserPolicyBody());   // AI Guard off
        await w.RunOnceAsync(t0.AddHours(1), default);
        Assert.Empty(_api.Drives[^1]);
    }

    [Fact]
    public async Task Approvals_are_fetched_only_where_the_org_asks_for_them()
    {
        var w = Worker();
        var t0 = new DateTime(2026, 11, 17, 9, 0, 0, DateTimeKind.Utc);
        _api.Next = Policy(1);                                            // log mode
        await w.RunOnceAsync(t0, default);
        await w.RunOnceAsync(t0.AddMinutes(1), default);
        Assert.Equal(0, _api.ApprovalFetches);                            // no extra call on an ordinary PC
        Assert.Empty(Assert.Single(_stored));                             // leftovers of an earlier run cleared once

        var approve = new AgentBrowserPolicy(2, new AgentBrowserPolicyBody(GuardMode: "approve", ChromeExtensionId: "abcdefghijklmnopabcdefghijklmnop"));
        _api.Next = approve;
        _api.Approvals = [new(@"PC\asha", "chatgpt.com", "paste", DateTimeOffset.UtcNow.AddMinutes(30))];
        await w.RunOnceAsync(t0.AddHours(1), default);
        await w.RunOnceAsync(t0.AddHours(1).AddMinutes(1), default);
        Assert.Equal(2, _api.ApprovalFetches);                            // every cycle while asked for
        Assert.Equal("chatgpt.com", _stored[^1].Single().Site);

        _api.Approvals = null;                                            // backend unreachable: keep what is stored
        await w.RunOnceAsync(t0.AddHours(1).AddMinutes(2), default);
        Assert.Equal(3, _stored.Count);
    }

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
    public async Task A_usb_write_window_is_asked_for_only_on_request_and_ends_by_itself()
    {
        var w = Worker();
        var t0 = new DateTime(2026, 11, 19, 9, 0, 0, DateTimeKind.Utc);
        _api.Next = new AgentBrowserPolicy(1, new AgentBrowserPolicyBody(UsbMode: "read_only"));
        await w.RunOnceAsync(t0, default);
        Assert.Equal(0, _api.UsbWindowFetches);                          // no extra call outside on_request

        var until = DateTimeOffset.UtcNow.AddMinutes(30);
        _api.Next = new AgentBrowserPolicy(2, new AgentBrowserPolicyBody(UsbMode: "on_request"));
        _api.UsbWindow = new(until);
        await w.RunOnceAsync(t0.AddHours(1), default);
        Assert.Equal(until.UtcDateTime, _applied[^1].UsbWriteUntil);
        Assert.Empty(BrowserPolicyMap.Usb(_applied[^1], DateTime.UtcNow));         // writing allowed now
        Assert.NotEmpty(BrowserPolicyMap.Usb(_applied[^1], until.UtcDateTime.AddSeconds(1)));   // and not after, offline or not

        _api.UsbWindow = null;                                            // backend unreachable: keep what is known
        await w.RunOnceAsync(t0.AddHours(1).AddMinutes(1), default);
        Assert.Equal(until.UtcDateTime, _applied[^1].UsbWriteUntil);
        _api.UsbWindow = new(null);                                       // IT closed it early
        await w.RunOnceAsync(t0.AddHours(1).AddMinutes(2), default);
        Assert.Null(_applied[^1].UsbWriteUntil);
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
