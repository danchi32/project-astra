using AstraAgent.Service;
using AstraAgent.Service.Api;
using AstraAgent.Service.Guard;
using Microsoft.Extensions.Logging.Abstractions;
using Microsoft.Extensions.Options;
using Xunit;

namespace AstraAgent.Service.Tests;

/// <summary>
/// Phase 3 · D10: browsers the policy cannot reach are closed when the org asks, and only
/// those: a process is one only if its exe name and its file's own name agree. The process
/// list, kill and notice are replaced, so nothing here closes a real program.
/// </summary>
public class OtherBrowsersTests
{
    [Theory]
    [InlineData("opera", "Opera Norway AS", "Opera GX", @"C:\Users\a\AppData\Local\Programs\Opera GX\opera.exe", "Opera")]
    [InlineData("Brave", "Brave Software, Inc.", "Brave Browser", null, "Brave")]
    [InlineData("browser", "YANDEX LLC", "Yandex", null, "Yandex Browser")]
    [InlineData("firefox", "Mozilla Corporation", "Firefox", @"C:\Users\a\Desktop\Tor Browser\Browser\firefox.exe", "Tor Browser")]
    [InlineData("chrome", "The Chromium Authors", "Chromium", null, "Chromium")]
    // Never these:
    [InlineData("chrome", "Google LLC", "Google Chrome", @"C:\Program Files\Google\Chrome\Application\chrome.exe", null)]
    [InlineData("firefox", "Mozilla Corporation", "Firefox", @"C:\Program Files\Mozilla Firefox\firefox.exe", null)]
    [InlineData("msedge", "Microsoft Corporation", "Microsoft Edge", null, null)]
    [InlineData("browser", "Some Vendor", "Kiosk", @"C:\Kiosk\browser.exe", null)]
    [InlineData("opera", null, null, null, null)]                      // file unreadable: left alone
    [InlineData("notepad", "Opera Norway AS", "Opera", null, null)]    // the name must match too
    public void Only_a_known_browser_by_name_and_by_its_own_file_matches(
        string process, string? company, string? product, string? path, string? expected) =>
        Assert.Equal(expected, OtherBrowsers.Match(process, company, product, path));

    [Fact]
    public void A_portable_browser_renamed_is_found_by_its_files_own_name()
    {
        // Review 3b L1: brave.exe copied to AppData as notes.exe is still Brave by its version info.
        Assert.Equal("Brave", OtherBrowsers.Match("notes", "Brave Software, Inc.", "Brave Browser",
                                                  @"C:\Users\a\AppData\Local\x\notes.exe", "brave.exe"));
        Assert.Null(OtherBrowsers.Match("notes", "Microsoft Corporation", "Notepad", null, "notepad.exe"));
    }

    readonly BrowserPolicyWorkerTests.Api _api = new();
    readonly SubscriptionState _subscription = new();
    readonly List<int> _killed = [];
    readonly List<(int Session, string Name)> _notices = [];
    List<RunningProcess> _running = [];

    BrowserPolicyWorker PolicyWorker() => new(new BrowserPolicyWorkerTests.Enrollment(), _api, _subscription,
        Options.Create(new AgentOptions()), NullLogger<BrowserPolicyWorker>.Instance)
    {
        Apply = _ => [],
        StoreApprovals = _ => { },
        ReapplyUsb = _ => 0,   // never the real USB drives of the PC running the tests
        UsbAppliedFile = Path.Combine(Path.GetTempPath(), "savio-usb-" + Guid.NewGuid().ToString("N")),
    };

    OtherBrowserBlocker Blocker(BrowserPolicyWorker policy) => new(policy, _subscription, NullLogger<OtherBrowserBlocker>.Instance)
    {
        List = () => _running,
        Kill = p => { _killed.Add(p.Id); return true; },
        Notify = (s, n) => _notices.Add((s, n)),
    };

    static RunningProcess Opera(int id, int session = 1) =>
        new(id, session, "opera", "Opera Norway AS", "Opera", @"C:\Users\a\AppData\Local\Programs\Opera\opera.exe");

    [Fact]
    public async Task Closed_only_when_the_policy_says_so_counted_once_per_start_and_reported()
    {
        var policy = PolicyWorker();
        var blocker = Blocker(policy);
        var t0 = new DateTime(2026, 11, 18, 9, 0, 0, DateTimeKind.Utc);
        _running = [Opera(10), Opera(11), Opera(12),
                    new(20, 1, "chrome", "Google LLC", "Google Chrome", @"C:\Program Files\Google\Chrome\Application\chrome.exe")];

        blocker.Sweep(t0);                                                  // no policy yet: nothing
        _api.Next = new AgentBrowserPolicy(5, new AgentBrowserPolicyBody(BlockOtherBrowsers: false));
        await policy.RunOnceAsync(t0, default);
        blocker.Sweep(t0);                                                  // policy without it: nothing
        Assert.Empty(_killed);

        _api.Next = new AgentBrowserPolicy(6, new AgentBrowserPolicyBody(BlockOtherBrowsers: true));
        await policy.RunOnceAsync(t0.AddHours(1), default);
        blocker.Sweep(t0.AddHours(1));
        Assert.Equal([10, 11, 12], _killed);                                // every Opera process, never Chrome
        Assert.Equal([(1, "Opera")], _notices);

        blocker.Sweep(t0.AddHours(1).AddSeconds(2));                        // started again at once
        Assert.Single(_notices);                                            // one notice a minute, not a stack of them
        blocker.Sweep(t0.AddHours(1).AddMinutes(2));
        Assert.Equal(2, _notices.Count);

        await policy.RunOnceAsync(t0.AddHours(1).AddMinutes(2), default);
        Assert.Equal(new Dictionary<string, int> { ["Opera"] = 3 }, _api.Closed[^1]);   // three starts, not nine processes
        await policy.RunOnceAsync(t0.AddHours(1).AddMinutes(3), default);
        Assert.Equal(new Dictionary<string, int> { ["Opera"] = 3 }, _api.Closed[^1]);   // sent once: nothing new to report
    }

    [Fact]
    public async Task Counts_are_kept_until_the_backend_has_them_and_a_dormant_org_closes_nothing()
    {
        var policy = PolicyWorker();
        var blocker = Blocker(policy);
        var t0 = new DateTime(2026, 11, 18, 9, 0, 0, DateTimeKind.Utc);
        _api.Next = new AgentBrowserPolicy(6, new AgentBrowserPolicyBody(BlockOtherBrowsers: true));
        await policy.RunOnceAsync(t0, default);
        _running = [Opera(10, session: 2)];

        blocker.Sweep(t0);
        _api.ReportAccepted = false;
        await policy.RunOnceAsync(t0.AddMinutes(1), default);
        _api.ReportAccepted = true;
        blocker.Sweep(t0.AddMinutes(1));
        await policy.RunOnceAsync(t0.AddMinutes(2), default);
        Assert.Equal(new Dictionary<string, int> { ["Opera"] = 2 }, _api.Closed[^1]);   // the failed report's close was not lost

        _subscription.Set(dormant: true);
        _killed.Clear();
        blocker.Sweep(t0.AddMinutes(3));
        Assert.Empty(_killed);
    }
}
