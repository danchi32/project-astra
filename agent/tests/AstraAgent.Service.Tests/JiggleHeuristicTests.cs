using System.Collections.Generic;
using AstraAgent.Service.Workforce;
using Xunit;

namespace AstraAgent.Service.Tests;

public class JiggleHeuristicTests
{
    // A jiggler: ~20 polls bouncing between two nearby points, never clicking.
    private static List<(int, int)> Jiggle()
    {
        var p = new List<(int, int)>();
        for (int i = 0; i < 10; i++) { p.Add((100, 100)); p.Add((102, 100)); }
        return p;
    }

    // Real work: the cursor visits many different places.
    private static List<(int, int)> Varied()
    {
        var p = new List<(int, int)>();
        for (int i = 0; i < 20; i++) p.Add((i * 13, i * 7));
        return p;
    }

    [Fact]
    public void No_data_is_idle()
    {
        Assert.Equal(InputQuality.Idle, JiggleHeuristic.Classify(new List<(int, int)>(), 0));
    }

    [Fact]
    public void A_still_cursor_is_idle()
    {
        var still = new List<(int, int)>();
        for (int i = 0; i < 10; i++) still.Add((500, 500));
        Assert.Equal(InputQuality.Idle, JiggleHeuristic.Classify(still, 0));
    }

    [Fact]
    public void Sustained_tiny_movement_with_no_clicks_is_suspect()
    {
        Assert.Equal(InputQuality.Suspect, JiggleHeuristic.Classify(Jiggle(), 0));
    }

    [Fact]
    public void The_same_movement_with_a_click_is_real()
    {
        // A single real click is enough to clear suspicion — the heuristic never accuses when
        // there is any sign of genuine interaction.
        Assert.Equal(InputQuality.Real, JiggleHeuristic.Classify(Jiggle(), 1));
    }

    [Fact]
    public void Varied_movement_across_the_screen_is_real()
    {
        Assert.Equal(InputQuality.Real, JiggleHeuristic.Classify(Varied(), 0));
    }

    [Fact]
    public void Moving_once_then_resting_is_not_suspect()
    {
        // Two distinct points but only ONE transition — someone nudged the mouse and stopped,
        // not a jiggler. Not sustained, so not flagged.
        var p = new List<(int, int)>();
        for (int i = 0; i < 5; i++) p.Add((100, 100));
        for (int i = 0; i < 5; i++) p.Add((400, 400));
        Assert.Equal(InputQuality.Real, JiggleHeuristic.Classify(p, 0));
    }

    [Fact]
    public void Too_little_data_is_not_flagged()
    {
        // Below the minimum poll count there isn't enough to judge — never flag on thin data.
        var p = new List<(int, int)> { (1, 1), (2, 1), (1, 1) };
        Assert.NotEqual(InputQuality.Suspect, JiggleHeuristic.Classify(p, 0));
    }
}
