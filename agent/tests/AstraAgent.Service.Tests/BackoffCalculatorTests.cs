using AstraAgent.Service.Workers;
using Xunit;

namespace AstraAgent.Service.Tests;

public class BackoffCalculatorTests
{
    private static readonly TimeSpan BaseInterval = TimeSpan.FromSeconds(60);
    private static readonly TimeSpan Max = TimeSpan.FromMinutes(15);

    [Fact]
    public void NoFailures_ReturnsBaseInterval()
    {
        Assert.Equal(BaseInterval, BackoffCalculator.NextDelay(0, BaseInterval, Max));
    }

    [Fact]
    public void FailuresDoubleTheDelay()
    {
        Assert.Equal(TimeSpan.FromSeconds(120), BackoffCalculator.NextDelay(1, BaseInterval, Max));
        Assert.Equal(TimeSpan.FromSeconds(240), BackoffCalculator.NextDelay(2, BaseInterval, Max));
    }

    [Fact]
    public void DelayIsCappedAtMax()
    {
        Assert.Equal(Max, BackoffCalculator.NextDelay(10, BaseInterval, Max));
        Assert.Equal(Max, BackoffCalculator.NextDelay(100, BaseInterval, Max));
    }

    [Fact]
    public void NegativeFailures_ReturnsBaseInterval()
    {
        Assert.Equal(BaseInterval, BackoffCalculator.NextDelay(-1, BaseInterval, Max));
    }
}
