namespace AstraAgent.Service.Telemetry.Collectors;

/// <summary>What an update is actually doing, matching what the user sees on the Windows
/// Update settings page. A bool could only say installed or not, so a device that had
/// installed everything and needed a reboot looked exactly like one that had never patched,
/// and an update whose download kept failing looked like one nobody had pushed yet.</summary>
public static class UpdateState
{
    public const string Pending = "pending";
    public const string PendingRestart = "pending_restart";
    public const string Failed = "failed";
    public const string Installed = "installed";
}

/// <param name="ErrorCode">Windows' own failure code, e.g. "0x80244018". Set only when the
/// state is failed — without it the portal can say something failed but not why, which
/// leaves the operator having to walk to the machine anyway.</param>
public sealed record WindowsUpdateEntry(
    string KbArticleId,
    string Title,
    bool IsInstalled,
    string? InstalledOn,
    string State = UpdateState.Pending,
    string? ErrorCode = null);

public interface IWindowsUpdateCollector
{
    IReadOnlyList<WindowsUpdateEntry> GetUpdates();
}
