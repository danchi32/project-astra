using AstraAgent.Service.Telemetry.Collectors;

namespace AstraAgent.Service.Workforce;

/// <summary>One presence transition the agent derived from the session enumeration.</summary>
public sealed record ActivityEvent(string Username, string Kind, DateTimeOffset OccurredAt, int? SessionId);

public interface IActivityTracker
{
    /// <summary>Compare this cycle's sessions with the last and emit the transitions between
    /// them. Stateful: remembers the previous set, so it must be a singleton.</summary>
    IReadOnlyList<ActivityEvent> Diff(IReadOnlyList<SessionInfo> current, DateTimeOffset now);
}

/// <summary>Turns the per-cycle WTS session enumeration (which the Service already collects
/// for the Sessions view) into Workforce Insights presence events — no new API call, no new
/// collector hitting the machine.
///
/// A session appearing signed-in is a <c>logon</c>; disappearing (or losing its user) is a
/// <c>logoff</c>. A logon carries the session's REAL logon time, so attendance is right even
/// when the agent first sees a session that signed in hours ago, or restarts mid-day.
///
/// State changes map to <c>lock</c>/<c>unlock</c>: active→disconnected is "stepped away"
/// (RDP closed, fast-user-switched), the reverse is "came back". Honest limitation: a console
/// Win+L lock does NOT change the WTS connect-state, so it is not seen here — that refinement
/// needs the Tray's own session-switch signal, which lands with the P2 idle work. For P1
/// attendance that only means a locked-but-signed-in console counts as worked, which is
/// exactly what the backend documents "worked" to mean until idle detection ships.</summary>
public sealed class ActivityTracker : IActivityTracker
{
    public const string Logon = "logon";
    public const string Logoff = "logoff";
    public const string Lock = "lock";
    public const string Unlock = "unlock";

    // sessionId -> (username last seen in it, last state). Username is null for a session
    // sitting at the logon screen. Empty on first call, so the first cycle emits a logon for
    // everyone already signed in — at their real logon time.
    private readonly Dictionary<int, (string? Username, string State)> _previous = new();

    public IReadOnlyList<ActivityEvent> Diff(IReadOnlyList<SessionInfo> current, DateTimeOffset now)
    {
        var events = new List<ActivityEvent>();
        var seen = new HashSet<int>();

        foreach (var s in current)
        {
            seen.Add(s.SessionId);
            var hadRow = _previous.TryGetValue(s.SessionId, out var prev);

            if (!string.IsNullOrWhiteSpace(s.Username))
            {
                if (!hadRow || prev.Username != s.Username)
                {
                    // A user not seen in this slot before. If a DIFFERENT user held it, they
                    // signed off first (switch-user reuses nothing, but a recycled session id
                    // could).
                    if (hadRow && !string.IsNullOrWhiteSpace(prev.Username))
                        events.Add(new ActivityEvent(prev.Username!, Logoff, now, s.SessionId));
                    events.Add(new ActivityEvent(s.Username!, Logon, s.LogonAt ?? now, s.SessionId));
                }
                else if (prev.State != s.State)
                {
                    if (s.State == "disconnected")
                        events.Add(new ActivityEvent(s.Username!, Lock, now, s.SessionId));
                    else if (s.State == "active")
                        events.Add(new ActivityEvent(s.Username!, Unlock, now, s.SessionId));
                }
            }
            else if (hadRow && !string.IsNullOrWhiteSpace(prev.Username))
            {
                // The session is still there but nobody is in it now — a console that signed
                // out to the logon screen. Its user logged off.
                events.Add(new ActivityEvent(prev.Username!, Logoff, now, s.SessionId));
            }

            _previous[s.SessionId] = (s.Username, s.State);
        }

        // Sessions that are gone entirely since last cycle — a signed-in user there logged off.
        foreach (var sessionId in _previous.Keys.Where(k => !seen.Contains(k)).ToList())
        {
            var prev = _previous[sessionId];
            if (!string.IsNullOrWhiteSpace(prev.Username))
                events.Add(new ActivityEvent(prev.Username!, Logoff, now, sessionId));
            _previous.Remove(sessionId);
        }

        return events;
    }
}
