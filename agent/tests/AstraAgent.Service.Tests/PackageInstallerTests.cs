using AstraAgent.Service.Remediation;
using Xunit;

namespace AstraAgent.Service.Tests;

public class PackageInstallerTests
{
    [Theory]
    [InlineData("Evil; rm -rf")]
    [InlineData("https://x/setup.exe")]
    [InlineData("nodot")]
    [InlineData("")]
    [InlineData(null)]
    public void Install_RefusesAnythingThatIsNotAWingetId(string? id)
    {
        var (ok, msg) = PackageInstaller.Install(id);
        Assert.False(ok);
        Assert.Contains("not a valid package id", msg);
    }

    [Fact]
    public void Describe_TreatsAlreadyInstalledAsSuccess()
    {
        Assert.True(PackageInstaller.Describe(0, "Google.Chrome", "").Item1);
        Assert.True(PackageInstaller.Describe(unchecked((int)0x8A15002B), "Google.Chrome", "").Item1);
        var (ok, msg) = PackageInstaller.Describe(unchecked((int)0x8A150014), "No.Such", "");
        Assert.False(ok);
        Assert.Contains("couldn't find", msg);
    }

    [Fact]
    public void Executor_AdvertisesInstall()
        => Assert.Contains("install_package", SystemRemediationExecutor.SupportedActions);
}

public class PackageInstallerNetworkTests
{
    [Fact]
    public void Describe_ExplainsABlockedDownload()
    {
        // 0x80072EE2, exactly as winget returned it on a real laptop where GitHub downloads timed out.
        var (ok, msg) = PackageInstaller.Describe(unchecked((int)0x80072EE2), "7zip.7zip", "InternetOpenUrl() failed.");
        Assert.False(ok);
        Assert.Contains("couldn't be downloaded", msg);
    }
}
