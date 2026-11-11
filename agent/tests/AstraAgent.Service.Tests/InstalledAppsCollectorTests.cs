using System.Text.Json;
using AstraAgent.Service.Api;
using AstraAgent.Service.Telemetry.Collectors;
using Microsoft.Extensions.Logging.Abstractions;
using Xunit;

namespace AstraAgent.Service.Tests;

public class InstalledAppsCollectorTests
{
    [Theory]
    [InlineData("S-1-5-21-3623811015-3361044348-30300820-1013", true)]   // local / AD account
    [InlineData("S-1-12-1-1234567890-1234567890-1234567890-1234567890", true)] // Entra-only account
    [InlineData("S-1-5-21-3623811015-3361044348-30300820-1013_Classes", false)] // file associations
    [InlineData(".DEFAULT", false)]
    [InlineData("S-1-5-18", false)] // LocalSystem
    [InlineData("S-1-5-19", false)] // LocalService
    [InlineData("S-1-5-20", false)] // NetworkService
    public void IsUserHive_AcceptsOnlyRealPeoplesProfiles(string keyName, bool expected)
        => Assert.Equal(expected, InstalledAppsCollector.IsUserHive(keyName));

    [Fact]
    public void GetInstalledApps_ReturnsMachineScopedAppsWithoutThrowing()
    {
        // Runs against this machine's real registry. Every Windows box has at least one
        // machine-wide install; the point is that per-user enumeration never breaks it.
        var apps = new InstalledAppsCollector(NullLogger<InstalledAppsCollector>.Instance).GetInstalledApps();

        Assert.Contains(apps, a => a.Scope == InstalledApp.MachineScope && a.UserName is null);
        Assert.All(apps.Where(a => a.Scope == InstalledApp.UserScope), a => Assert.False(string.IsNullOrEmpty(a.UserName)));
        Assert.All(apps, a => Assert.True(a.Name.Length <= 300 && a.Name == a.Name.Trim()));
    }

    [Fact]
    public void TelemetryInstalledApp_CarriesScopeAndUserOnTheWire()
    {
        var json = JsonSerializer.Serialize(new TelemetryInstalledApp(
            "ChatGPT", "1.2", "OpenAI", null, InstalledApp.UserScope, "ACME\\jdoe"));
        Assert.Contains("\"scope\":\"user\"", json);
        Assert.Contains("\"user_name\":\"ACME\\\\jdoe\"", json);
    }
}
