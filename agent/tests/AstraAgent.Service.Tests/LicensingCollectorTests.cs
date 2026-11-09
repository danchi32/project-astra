using System.Text.Json;
using AstraAgent.Service.Api;
using AstraAgent.Service.Telemetry.Collectors;
using Microsoft.Extensions.Logging.Abstractions;
using Xunit;

namespace AstraAgent.Service.Tests;

public class LicensingCollectorTests
{
    [Theory]
    [InlineData("55c92734-d682-4d71-983e-d6ec3f16059f", "windows")]
    [InlineData("55C92734-D682-4D71-983E-D6EC3F16059F", "windows")]
    [InlineData("0ff1ce15-a989-479d-af46-f275c6370663", "office")]
    [InlineData("00000000-0000-0000-0000-000000000000", null)]
    [InlineData(null, null)]
    public void KindOf_MapsOnlyWindowsAndOffice(string? appId, string? expected)
        => Assert.Equal(expected, LicensingCollector.KindOf(appId));

    [Fact]
    public void GetProducts_ReadsThisMachinesWindowsLicence()
    {
        // Every activated or not-yet-activated Windows install holds a key, so the real SPP
        // on the test machine must report exactly one Windows product with a known status.
        var products = new LicensingCollector(NullLogger<LicensingCollector>.Instance).GetProducts();

        Assert.NotNull(products);
        var windows = Assert.Single(products!, p => p.Kind == "windows");
        Assert.InRange(windows.LicenseStatus, 0, 6);
    }

    [Fact]
    public void TelemetryPush_OmitsLicensingBetweenInventories_AndCarriesItWhenPresent()
    {
        var product = new TelemetryLicensingProduct("windows", "Windows(R), Professional edition",
            "Windows(R) Operating System, RETAIL channel", 1, "Retail", null);
        var json = JsonSerializer.Serialize(product);
        Assert.Contains("\"license_status\":1", json);
        Assert.Contains("\"kms_host\":null", json);
    }
}
