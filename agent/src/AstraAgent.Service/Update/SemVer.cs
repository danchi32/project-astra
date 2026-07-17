namespace AstraAgent.Service.Update;

/// <summary>A minimal, dependency-free compare for the "MAJOR.MINOR.PATCH" versions the agent
/// ships with. Pre-release/build suffixes are ignored — releases the agent installs are plain
/// numeric versions. Anything unparseable sorts as 0.0.0 so a malformed value can never look
/// "newer" and trigger an unwanted update.</summary>
public static class SemVer
{
    /// <summary>True when <paramref name="candidate"/> is a strictly higher version than
    /// <paramref name="current"/>.</summary>
    public static bool IsNewer(string candidate, string current)
        => Compare(candidate, current) > 0;

    public static int Compare(string a, string b)
    {
        var (aj, an, ap) = Parse(a);
        var (bj, bn, bp) = Parse(b);
        if (aj != bj) return aj.CompareTo(bj);
        if (an != bn) return an.CompareTo(bn);
        return ap.CompareTo(bp);
    }

    private static (int Major, int Minor, int Patch) Parse(string version)
    {
        if (string.IsNullOrWhiteSpace(version))
            return (0, 0, 0);

        // Drop any pre-release/build metadata ("-beta", "+build") and a leading "v".
        var core = version.Trim().TrimStart('v', 'V');
        var cut = core.IndexOfAny(new[] { '-', '+' });
        if (cut >= 0)
            core = core[..cut];

        var parts = core.Split('.');
        int At(int i) => i < parts.Length && int.TryParse(parts[i], out var n) && n >= 0 ? n : 0;
        return (At(0), At(1), At(2));
    }
}
