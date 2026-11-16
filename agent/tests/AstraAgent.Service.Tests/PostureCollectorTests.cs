using AstraAgent.Service.Telemetry.Collectors;
using Xunit;

namespace AstraAgent.Service.Tests;

/// <summary>2a — the WMI values, read the way the backend needs them: a null is "unknown", a
/// 0 is "off", and nothing a WMI class sends can smuggle a wrong value through.</summary>
public class PostureCollectorTests
{
    [Theory]
    [InlineData(true, true)]
    [InlineData(false, false)]
    [InlineData(1, true)]          // firewall Enabled comes as an integer
    [InlineData((ushort)0, false)]
    [InlineData((byte)1, true)]
    [InlineData(2, null)]          // GpoBoolean NotConfigured: says nothing about the state
    [InlineData("garbage", null)]
    [InlineData(null, null)]
    public void ParseBool_KnowsOnFromOffAndNeverGuesses(object? value, bool? expected)
        => Assert.Equal(expected, PostureCollector.ParseBool(value));

    [Theory]
    [InlineData((uint)0, 0)]
    [InlineData((uint)7, 7)]
    [InlineData((uint)3650, 3650)]
    [InlineData((uint)3651, null)]  // implausible: refused rather than sent
    [InlineData(null, null)]
    public void ParseAgeDays_OnlyPlausibleWholeDays(object? value, int? expected)
        => Assert.Equal(expected, PostureCollector.ParseAgeDays(value));

    [Theory]
    [InlineData(1, true)]   // On
    [InlineData(0, false)]  // Off
    [InlineData(2, null)]   // Unknown
    [InlineData(null, null)]
    public void ParseProtectionStatus_FollowsWin32Encryptable(object? value, bool? expected)
        => Assert.Equal(expected, PostureCollector.ParseProtectionStatus(value));

    [Theory]
    [InlineData(@"C:\Windows\System32", "C:")]
    [InlineData(@"d:\windows\system32", "D:")]
    public void SystemDriveLetter_IsAPlainDriveLetter(string dir, string expected)
        => Assert.Equal(expected, PostureCollector.SystemDriveLetter(dir));

    [Theory]
    [InlineData(@"\\server\share")]           // UNC: no drive letter at all
    [InlineData("")]
    public void SystemDriveLetter_RefusesAnythingElse(string dir)
        => Assert.Null(PostureCollector.SystemDriveLetter(dir));

    [Fact]
    public void SystemDriveLetter_NeverCarriesQuerySyntaxIntoTheWql()
    {
        // The path root keeps only "C:" from this hostile value, so what reaches the WQL is a
        // plain drive letter, never the quote-and-OR text that followed it.
        Assert.Equal("C:", PostureCollector.SystemDriveLetter("C:' OR '1'='1"));
    }
}
