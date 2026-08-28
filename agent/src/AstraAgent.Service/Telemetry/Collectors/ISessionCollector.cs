namespace AstraAgent.Service.Telemetry.Collectors;

/// <summary>One Windows logon session as the agent sees it.</summary>
/// <param name="SessionId">Windows' own session id — the handle every session action uses.</param>
/// <param name="Username">DOMAIN\user, or null when nobody is signed into the session.</param>
/// <param name="State">"active" or "disconnected".</param>
/// <param name="Connection">"console" or "rdp".</param>
/// <param name="Station">The WinStation name, e.g. "Console" or "RDP-Tcp#3".</param>
/// <param name="ClientName">For an RDP session, the machine it is coming from.</param>
/// <param name="LogonAt">When the session signed in, or null if Windows didn't say.</param>
/// <param name="IdleSeconds">Seconds since the session last saw input, or null.</param>
public sealed record SessionInfo(
    int SessionId,
    string? Username,
    string State,
    string Connection,
    string? Station,
    string? ClientName,
    DateTimeOffset? LogonAt,
    int? IdleSeconds);

public interface ISessionCollector
{
    IReadOnlyList<SessionInfo> GetSessions();
}
