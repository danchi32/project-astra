using AstraAgent.Service.Remediation;
using Xunit;

namespace AstraAgent.Service.Tests;

/// <summary>enable_firewall — the read-back must see ON on all three profiles before the fix counts.</summary>
public class FirewallRemediationTests
{
    // The shape of `netsh advfirewall show allprofiles state`: one "State" line per profile.
    private static string Report(params (string Profile, string State)[] profiles) =>
        string.Join("\n\n", profiles.Select(p =>
            $"{p.Profile} Profile Settings:\n-----\nState                                 {p.State}"));

    [Fact]
    public void AllOn_IsTrueOnlyWhenEveryProfileReportsOn()
        => Assert.True(FirewallRemediation.AllOn(Report(
            ("Domain", "ON"), ("Private", "ON"), ("Public", "ON"))));

    [Fact]
    public void AllOn_IsFalseIfAnyProfileIsStillOff()
        => Assert.False(FirewallRemediation.AllOn(Report(
            ("Domain", "ON"), ("Private", "OFF"), ("Public", "ON"))));

    [Fact]
    public void AllOn_IsFalseIfAProfileIsMissingFromTheOutput()
        => Assert.False(FirewallRemediation.AllOn(Report(("Domain", "ON"), ("Private", "ON"))));

    [Fact]
    public void AllOn_IsFalseForEmptyOrUnreadableOutput()
    {
        Assert.False(FirewallRemediation.AllOn(""));
        Assert.False(FirewallRemediation.AllOn("Access is denied."));
    }

    [Fact]
    public void TheExecutorAdvertisesIt()
        => Assert.Contains("enable_firewall", SystemRemediationExecutor.SupportedActions);
}
