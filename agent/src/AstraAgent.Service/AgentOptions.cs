namespace AstraAgent.Service;

public sealed class AgentOptions
{
    public const string SectionName = "Astra";

    /// <summary>Base URL of the ASTRA backend, e.g. https://astra.example.com</summary>
    public string ServerUrl { get; set; } = string.Empty;

    /// <summary>One-time enrollment token issued by an admin; only consulted until
    /// a device credential has been stored.</summary>
    public string? EnrollmentToken { get; set; }

    public int HeartbeatIntervalSeconds { get; set; } = 60;
}

public static class AgentVersion
{
    public const string Current = "0.1.0";
}
