using AstraAgent.Service.Telemetry.Collectors;
using Xunit;

namespace AstraAgent.Service.Tests;

public class EventLogCollectorTests
{
    [Fact]
    public void ToOffset_NullTime_ReturnsUtcNowish()
    {
        var before = DateTimeOffset.UtcNow.AddSeconds(-1);
        var result = EventLogCollector.ToOffset(null);
        Assert.True(result >= before);
        Assert.Equal(TimeSpan.Zero, result.Offset);
    }

    [Fact]
    public void ToOffset_LocalTime_DoesNotThrow_AndIsUtc()
    {
        // A local DateTime (as EventRecord.TimeCreated reports) must not throw.
        var local = new DateTime(2026, 7, 8, 10, 30, 0, DateTimeKind.Local);
        var result = EventLogCollector.ToOffset(local);
        Assert.Equal(TimeSpan.Zero, result.Offset);
        Assert.Equal(local.ToUniversalTime(), result.UtcDateTime);
    }

    [Fact]
    public void ToOffset_UnspecifiedTime_TreatedAsLocal()
    {
        var unspecified = new DateTime(2026, 7, 8, 10, 30, 0, DateTimeKind.Unspecified);
        var result = EventLogCollector.ToOffset(unspecified);
        Assert.Equal(TimeSpan.Zero, result.Offset);
    }

    [Fact]
    public void ToOffset_UtcTime_PreservedAsZeroOffset()
    {
        var utc = new DateTime(2026, 7, 8, 10, 30, 0, DateTimeKind.Utc);
        var result = EventLogCollector.ToOffset(utc);
        Assert.Equal(TimeSpan.Zero, result.Offset);
        Assert.Equal(utc, result.UtcDateTime);
    }
}
