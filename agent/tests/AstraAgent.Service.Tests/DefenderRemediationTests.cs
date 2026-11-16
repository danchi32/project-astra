using AstraAgent.Service.Remediation;
using Xunit;

namespace AstraAgent.Service.Tests;

/// <summary>enable_defender_realtime — the action only runs when Defender is the one antivirus.</summary>
public class DefenderRemediationTests
{
    [Theory]
    [InlineData("Windows Defender")]
    [InlineData("Microsoft Defender Antivirus")]
    public void Defender_alone_is_sole(string name)
        => Assert.True(DefenderRemediation.IsDefenderSole([name]));

    [Fact]
    public void A_third_party_antivirus_means_not_sole()
        => Assert.False(DefenderRemediation.IsDefenderSole(["Windows Defender", "CrowdStrike Falcon"]));

    [Fact]
    public void A_third_party_antivirus_alone_means_not_sole()
        => Assert.False(DefenderRemediation.IsDefenderSole(["Bitdefender Antivirus"]));

    [Fact]
    public void An_empty_list_is_not_proof_that_defender_is_the_only_one()
        => Assert.False(DefenderRemediation.IsDefenderSole([]));
}
