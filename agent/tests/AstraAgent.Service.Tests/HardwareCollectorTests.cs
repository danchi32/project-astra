using System.Text.Json;
using AstraAgent.Service.Api;
using AstraAgent.Service.Telemetry.Collectors;
using Xunit;

namespace AstraAgent.Service.Tests;

public class HardwareBiosTests
{
    [Theory]
    [InlineData("20230515000000.000000+000", "2023-05-15")]
    [InlineData("20191231", "2019-12-31")]
    [InlineData("garbage!", null)]
    [InlineData("", null)]
    [InlineData(null, null)]
    public void ToIsoDate_ReadsCimDates(string? cim, string? expected)
        => Assert.Equal(expected, HardwareCollector.ToIsoDate(cim));

    [Fact]
    public void TelemetryHardware_CarriesBiosFields()
    {
        var json = JsonSerializer.Serialize(new TelemetryHardware("Dell Inc.", "Latitude 5440", null, 16384, 512,
            "ABC1234", "1.18.0", "2024-03-01"));
        Assert.Contains("\"serial_number\":\"ABC1234\"", json);
        Assert.Contains("\"bios_version\":\"1.18.0\"", json);
        Assert.Contains("\"bios_release_date\":\"2024-03-01\"", json);
    }
}
