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
    /// <summary>The version this binary was built as, read from the assembly rather than written
    /// out by hand. It used to be a literal that had to be kept in step with two csproj
    /// <c>&lt;Version&gt;</c> elements; nothing enforced that at build time, so the constant and
    /// the assembly could disagree and an installer could be stamped with one version while
    /// carrying binaries of another. Deriving it removes that class of mistake entirely — the
    /// number now has exactly one source, src/Directory.Build.props.
    ///
    /// Three components only: the fourth in a .NET assembly version is always zero here, and
    /// SemVer ignores it anyway.</summary>
    public static readonly string Current = Resolve();

    private static string Resolve()
    {
        var v = typeof(AgentVersion).Assembly.GetName().Version;
        // 0.0.0 is deliberately unusable: it loses every SemVer comparison, so a build that
        // somehow lost its version can never look newer than what a device already runs.
        return v is null ? "0.0.0" : $"{v.Major}.{v.Minor}.{v.Build}";
    }
}
