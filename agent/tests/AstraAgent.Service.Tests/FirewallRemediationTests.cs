using AstraAgent.Service.Remediation;
using AstraAgent.Service.Telemetry.Collectors;
using Xunit;

namespace AstraAgent.Service.Tests;

/// <summary>enable_firewall — success needs all three profiles known and on in the EFFECTIVE state,
/// and the action never runs beside another registered firewall.</summary>
public class FirewallRemediationTests
{
    [Fact]
    public void AllOn_needs_every_profile_on()
        => Assert.True(FirewallRemediation.AllOn((true, true, true)));

    [Theory]
    [InlineData(true, false, true)]   // one still off (a Group Policy keeps it off)
    [InlineData(true, true, null)]    // one not reported: not proof it is on
    [InlineData(null, null, null)]
    public void AllOn_is_false_otherwise(bool? domain, bool? priv, bool? pub)
        => Assert.False(FirewallRemediation.AllOn((domain, priv, pub)));

    [Fact]
    public void Windows_firewall_itself_is_not_another_firewall()
        => Assert.Empty(FirewallRemediation.OtherFirewalls(["Windows Firewall", "Microsoft Defender Firewall", ""]));

    [Fact]
    public void A_third_party_firewall_is_named()
        => Assert.Equal(["ZoneAlarm Firewall"], FirewallRemediation.OtherFirewalls(["ZoneAlarm Firewall"]));

    [Fact]
    public void TheExecutorAdvertisesIt()
        => Assert.Contains("enable_firewall", SystemRemediationExecutor.SupportedActions);

    [Fact]
    public void Posture_knows_when_another_antivirus_is_registered()
    {
        Assert.True(PostureCollector.HasThirdPartyAntivirus(["Windows Defender", "Bitdefender Antivirus"]));
        Assert.False(PostureCollector.HasThirdPartyAntivirus(["Windows Defender"]));
        Assert.False(PostureCollector.HasThirdPartyAntivirus([]));
    }
}
