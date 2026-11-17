using System.Text.Json;
using System.Text.Json.Serialization;
using System.Text.RegularExpressions;

namespace AstraAgent.Guard;

/// <summary>
/// Phase 3 · E3 / E4: one thing the browser extension saw, as it travels from the native host
/// to the SAVIO service and on to the backend.
///
/// The schema is fixed and has no free-text field: a host name, three words from short lists,
/// counts per kind of finding, and flags. Unknown properties are refused, not ignored, so
/// nothing can be added to this message without changing this file. It never carries the
/// text that was checked, not even a piece of it. Who did it is not in here either: the service
/// takes that from Windows (the pipe client's identity), not from anything the browser says.
/// </summary>
public sealed record GuardEvent(
    string Site,
    string Channel,
    string Mode,
    string Action,
    IReadOnlyDictionary<string, int> Counts,
    bool ContactList,
    int KeywordHits,
    bool Unknown)
{
    /// <summary>Largest message accepted on the pipe. A real event is about 200 bytes.</summary>
    public const int MaxBytes = 2048;

    public static readonly string[] Channels = ["paste", "drop", "file", "submit"];
    public static readonly string[] Modes = ["log", "warn", "block"];
    public static readonly string[] Actions = ["allow", "warn", "block"];
    public static readonly string[] Kinds = Enum.GetNames<Finding>();

    // Host names only: letters, digits, dots and hyphens. Intranet names without a dot allowed.
    static readonly Regex Host = new("^[a-z0-9]([a-z0-9.-]{0,251}[a-z0-9])?$", RegexOptions.CultureInvariant);

    public static readonly JsonSerializerOptions Json = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
        UnmappedMemberHandling = JsonUnmappedMemberHandling.Disallow,
    };

    /// <summary>True when something was found, or the check could not be done. Anything else is
    /// an ordinary paste and is not recorded at all.</summary>
    public bool Notable => Unknown || ContactList || KeywordHits > 0 || Counts.Values.Any(n => n > 0);

    public bool IsValid() =>
        Site is not null && Host.IsMatch(Site) &&
        Channels.Contains(Channel) && Modes.Contains(Mode) && Actions.Contains(Action) &&
        Counts is not null && Counts.Count <= Kinds.Length &&
        Counts.All(kv => Kinds.Contains(kv.Key) && kv.Value is >= 0 and <= 1_000_000) &&
        KeywordHits is >= 0 and <= 200;

    /// <summary>The event in <paramref name="json"/>, or null if it is not exactly this shape.</summary>
    public static GuardEvent? Parse(ReadOnlySpan<byte> json)
    {
        if (json.Length > MaxBytes) return null;
        try
        {
            var e = JsonSerializer.Deserialize<GuardEvent>(json, Json);
            return e is not null && e.IsValid() ? e : null;
        }
        catch (JsonException) { return null; }
    }

    public byte[] ToJson() => JsonSerializer.SerializeToUtf8Bytes(this, Json);
}
