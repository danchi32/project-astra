namespace AstraAgent.Service.Workforce;

/// <summary>How the mouse input in a sampling window looks.</summary>
public enum InputQuality
{
    /// <summary>The cursor did not move — no mouse activity to judge.</summary>
    Idle,

    /// <summary>Normal, varied mouse use (clicks, or movement across many places).</summary>
    Real,

    /// <summary>Movement that looks mechanical — sustained but confined to a few points with no
    /// clicks, the signature of a mouse jiggler keeping the session awake.</summary>
    Suspect,
}

/// <summary>Flags likely idle-faking from mouse movement alone — deliberately mouse-only, never
/// the keyboard, so nothing here comes near the "no keystroke logging" red line.
///
/// A signal for review, NOT a verdict: a human decides. It errs toward NOT accusing — real work
/// (any click, or movement spread across the screen) is never Suspect, so a false "faking" flag
/// is costly and this would rather miss a clever jiggler than wrongly accuse someone fidgeting.
///
/// The thresholds are first estimates and want field tuning; they are constants here for that
/// reason.</summary>
public static class JiggleHeuristic
{
    // A jiggler moves constantly but within a tiny set of points. Real use, over the same
    // window, visits many distinct places and usually clicks. Thresholds are a RATIO of the
    // poll count, not an absolute, so they hold whatever the window length / poll rate is.
    internal const int MinPolls = 5;         // too little data to judge below this
    internal const int FewDistinct = 6;      // it only ever sat at this few distinct points

    /// <summary>Classify one window of per-poll cursor positions (in order) plus the mouse
    /// clicks seen in that window.</summary>
    public static InputQuality Classify(IReadOnlyList<(int X, int Y)> positions, int clicks)
    {
        if (positions.Count == 0)
            return InputQuality.Idle;

        var distinct = new HashSet<(int, int)>();
        int moves = 0;
        for (int i = 0; i < positions.Count; i++)
        {
            distinct.Add(positions[i]);
            if (i > 0 && positions[i] != positions[i - 1])
                moves++;
        }

        if (moves == 0)
            return InputQuality.Idle;          // cursor sat still the whole window
        if (clicks > 0)
            return InputQuality.Real;          // a real interaction — never flag it

        // Moved, but never clicked: suspect only when the movement is BOTH sustained (it moved
        // on at least half the polls) AND confined (few distinct points) — bouncing between a
        // handful of spots, which is what a jiggler does and real work does not.
        if (positions.Count >= MinPolls && moves * 2 >= positions.Count && distinct.Count <= FewDistinct)
            return InputQuality.Suspect;

        return InputQuality.Real;
    }
}
