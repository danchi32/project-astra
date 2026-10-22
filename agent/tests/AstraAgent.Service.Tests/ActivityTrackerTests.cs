using AstraAgent.Service.Telemetry.Collectors;
using AstraAgent.Service.Workforce;
using Xunit;

namespace AstraAgent.Service.Tests;

public class ActivityTrackerTests
{
    private static readonly DateTimeOffset Now = new(2026, 7, 7, 18, 0, 0, TimeSpan.Zero);

    private static SessionInfo Sess(
        int id, string? user, string state = "active", DateTimeOffset? logon = null) =>
        new(id, user, state, "console", "Console", null, logon, null);

    [Fact]
    public void FirstSightOfASignedInSession_IsALogonAtItsRealLogonTime()
    {
        var tracker = new ActivityTracker();
        var logon = new DateTimeOffset(2026, 7, 7, 9, 0, 0, TimeSpan.Zero);

        var events = tracker.Diff([Sess(1, "ACME\\rahul", logon: logon)], Now);

        var e = Assert.Single(events);
        Assert.Equal(ActivityTracker.Logon, e.Kind);
        Assert.Equal("ACME\\rahul", e.Username);
        Assert.Equal(logon, e.OccurredAt);   // the session's real logon, not "now"
        Assert.Equal(1, e.SessionId);
    }

    [Fact]
    public void LogonFallsBackToNowWhenWindowsGivesNoLogonTime()
    {
        var tracker = new ActivityTracker();
        var e = Assert.Single(tracker.Diff([Sess(1, "ACME\\rahul", logon: null)], Now));
        Assert.Equal(Now, e.OccurredAt);
    }

    [Fact]
    public void AnUnchangedSessionEmitsNothingOnTheNextCycle()
    {
        var tracker = new ActivityTracker();
        var logon = new DateTimeOffset(2026, 7, 7, 9, 0, 0, TimeSpan.Zero);
        tracker.Diff([Sess(1, "ACME\\rahul", logon: logon)], Now);

        Assert.Empty(tracker.Diff([Sess(1, "ACME\\rahul", logon: logon)], Now.AddMinutes(1)));
    }

    [Fact]
    public void ASessionDisappearing_IsALogoff()
    {
        var tracker = new ActivityTracker();
        tracker.Diff([Sess(1, "ACME\\rahul")], Now);

        var e = Assert.Single(tracker.Diff([], Now.AddMinutes(1)));
        Assert.Equal(ActivityTracker.Logoff, e.Kind);
        Assert.Equal("ACME\\rahul", e.Username);
        Assert.Equal(Now.AddMinutes(1), e.OccurredAt);
    }

    [Fact]
    public void AConsoleSessionSigningOutToTheLogonScreen_IsALogoff()
    {
        var tracker = new ActivityTracker();
        tracker.Diff([Sess(1, "ACME\\rahul")], Now);

        // Same session id survives, but nobody is in it now.
        var e = Assert.Single(tracker.Diff([Sess(1, null)], Now.AddMinutes(1)));
        Assert.Equal(ActivityTracker.Logoff, e.Kind);
        Assert.Equal("ACME\\rahul", e.Username);
    }

    [Fact]
    public void ActiveToDisconnected_IsLock_AndBack_IsUnlock()
    {
        var tracker = new ActivityTracker();
        tracker.Diff([Sess(1, "ACME\\rahul", state: "active")], Now);

        var locked = Assert.Single(tracker.Diff([Sess(1, "ACME\\rahul", state: "disconnected")], Now.AddMinutes(1)));
        Assert.Equal(ActivityTracker.Lock, locked.Kind);

        var unlocked = Assert.Single(tracker.Diff([Sess(1, "ACME\\rahul", state: "active")], Now.AddMinutes(2)));
        Assert.Equal(ActivityTracker.Unlock, unlocked.Kind);
    }

    [Fact]
    public void ADifferentUserInTheSameSessionId_LogsOffTheOldAndOnTheNew()
    {
        var tracker = new ActivityTracker();
        tracker.Diff([Sess(1, "ACME\\rahul")], Now);

        var events = tracker.Diff([Sess(1, "ACME\\sana", logon: Now.AddMinutes(1))], Now.AddMinutes(1));
        Assert.Equal(2, events.Count);
        Assert.Contains(events, e => e.Kind == ActivityTracker.Logoff && e.Username == "ACME\\rahul");
        Assert.Contains(events, e => e.Kind == ActivityTracker.Logon && e.Username == "ACME\\sana");
    }

    [Fact]
    public void ASessionWithNobodySignedIn_IsIgnored()
    {
        var tracker = new ActivityTracker();
        // The logon screen (session 1, no user) and services (session 0 is already filtered
        // upstream). Nothing attributable, so nothing is emitted.
        Assert.Empty(tracker.Diff([Sess(1, null)], Now));
    }

    [Fact]
    public void TwoConcurrentAccounts_AreTrackedIndependently()
    {
        var tracker = new ActivityTracker();
        tracker.Diff(
        [
            Sess(1, "ACME\\rahul", logon: Now),
            Sess(2, "ACME\\sana", logon: Now),
        ], Now);

        // rahul signs off, sana stays — only one logoff.
        var e = Assert.Single(tracker.Diff([Sess(2, "ACME\\sana", logon: Now)], Now.AddMinutes(1)));
        Assert.Equal(ActivityTracker.Logoff, e.Kind);
        Assert.Equal("ACME\\rahul", e.Username);
    }
}
