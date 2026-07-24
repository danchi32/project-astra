namespace AstraAgent.Service;

public sealed class AgentOptions
{
    public const string SectionName = "Astra";

    /// <summary>Base URL of the ASTRA backend, e.g. https://astra.example.com</summary>
    public string ServerUrl { get; set; } = string.Empty;

    /// <summary>One-time enrollment token issued by an admin; only consulted until
    /// a device credential has been stored.</summary>
    public string? EnrollmentToken { get; set; }

    /// <summary>Optional explicit outbound proxy (e.g. http://proxy.corp:8080) for locked-down
    /// networks. Left empty by default: the agent auto-detects the corporate proxy (machine
    /// config + WPAD/PAC) via the Windows HTTP stack, which works even under LocalSystem.</summary>
    public string? ProxyUrl { get; set; }

    public int HeartbeatIntervalSeconds { get; set; } = 60;

    /// <summary>How often the elevated service polls for approved system-context remediation
    /// tasks (machine-wide cleanup). Clamped to a 10s floor.</summary>
    public int RemediationPollSeconds { get; set; } = 30;

    /// <summary>How often to check the backend for a newer signed agent release. Auto-update
    /// stays off entirely unless a real signing public key is pinned into the build.</summary>
    public int UpdateCheckIntervalMinutes { get; set; } = 60;
}

public static class AgentVersion
{
    public const string Current = "0.6.3";
}
