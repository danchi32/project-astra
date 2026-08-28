using AstraAgent.Service.Sessions;

namespace AstraAgent.Service.Telemetry.Collectors;

/// <summary>Enumerates the machine's logon sessions via the WTS APIs.
///
/// The device already reports `logged_in_user` on every heartbeat and that stays: it is the
/// console user, it is what the device list shows, and on the single-user laptop that is most
/// of a fleet it is the whole truth. It stops being the truth the moment a machine has two
/// people on it — a terminal server, a shared workstation, an engineer signed in over RDP to
/// a machine somebody else is sitting at — and those are exactly the machines a technician
/// goes looking for.
///
/// Runs as LocalSystem in session 0, which is what makes it possible at all: a process inside
/// a user's session can only see its own.</summary>
public sealed class SessionCollector(ILogger<SessionCollector> logger) : ISessionCollector
{
    public IReadOnlyList<SessionInfo> GetSessions()
    {
        var sessions = new List<SessionInfo>();
        try
        {
            foreach (var raw in WtsNative.Enumerate())
            {
                // Session 0 is where services live. It has no desktop and nobody signs into
                // it, so including it would put a row on the portal's Sessions page for every
                // machine in the fleet that means nothing and can be acted on by mistake.
                if (raw.SessionId == 0)
                    continue;

                // Everything that is not Active or Disconnected is the terminal-services
                // stack talking to itself: listeners waiting for a connection, sessions
                // mid-handshake, shadow sessions. None of them is a person.
                if (raw.State != WtsNative.WtsActive && raw.State != WtsNative.WtsDisconnected)
                    continue;

                var info = WtsNative.QueryInfo(raw.SessionId);

                var user = info?.UserName?.Trim() ?? WtsNative.QueryString(raw.SessionId, WtsNative.WtsUserName);
                var domain = info?.Domain?.Trim() ?? WtsNative.QueryString(raw.SessionId, WtsNative.WtsDomainName);
                var station = !string.IsNullOrWhiteSpace(info?.WinStationName)
                    ? info!.Value.WinStationName.Trim()
                    : (raw.pWinStationName ?? WtsNative.QueryString(raw.SessionId, WtsNative.WtsWinStationName));
                var client = WtsNative.QueryString(raw.SessionId, WtsNative.WtsClientName);

                // A signed-out console session still exists and still gets enumerated — that
                // is the machine sitting at its logon screen. It is reported with no user
                // rather than dropped, because "nobody is on that machine" is a real and
                // frequently wanted answer, and dropping the row makes it indistinguishable
                // from a device that never reported.
                var username = string.IsNullOrWhiteSpace(user)
                    ? null
                    : string.IsNullOrWhiteSpace(domain) ? user : $"{domain}\\{user}";

                sessions.Add(new SessionInfo(
                    SessionId: raw.SessionId,
                    Username: username,
                    State: raw.State == WtsNative.WtsActive ? "active" : "disconnected",
                    Connection: WtsNative.ConnectionKind(station, client),
                    Station: string.IsNullOrWhiteSpace(station) ? null : Truncate(station, 60),
                    ClientName: string.IsNullOrWhiteSpace(client) ? null : Truncate(client, 120),
                    LogonAt: info is null ? null : WtsNative.FromFileTime(info.Value.LogonTime),
                    IdleSeconds: info is null ? null : IdleSeconds(info.Value)));
            }
        }
        catch (Exception ex)
        {
            // Never fatal. Sessions ride along with CPU/RAM/disk on the same push, and losing
            // a whole telemetry cycle because the session enumeration failed would trade the
            // metric that drives alerting for the one that drives a table.
            logger.LogWarning(ex, "Could not enumerate logon sessions");
            return [];
        }
        return sessions;
    }

    /// <summary>Seconds since this session last saw keyboard or mouse input.
    ///
    /// Windows reports LastInputTime as 0 on plenty of local sessions, and a 0 is not "idle
    /// since 1601" — it means the session never reported. Null travels to the portal as "—",
    /// which is honest; a number computed from that zero would read as 424 years idle.</summary>
    private static int? IdleSeconds(WtsNative.WTSINFO info)
    {
        if (info.LastInputTime <= 0 || info.CurrentTime <= 0) return null;
        var ticks = info.CurrentTime - info.LastInputTime;
        if (ticks < 0) return 0;
        var seconds = ticks / TimeSpan.TicksPerSecond;
        // Cap rather than overflow. A machine whose clock has moved can produce an absurd
        // difference, and an int that wrapped would arrive as a negative idle time.
        return seconds > int.MaxValue ? int.MaxValue : (int)seconds;
    }

    private static string Truncate(string value, int max) =>
        value.Length <= max ? value : value[..max];
}
