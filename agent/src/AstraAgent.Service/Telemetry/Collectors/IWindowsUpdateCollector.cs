namespace AstraAgent.Service.Telemetry.Collectors;

public sealed record WindowsUpdateEntry(string KbArticleId, string Title, bool IsInstalled, string? InstalledOn);

public interface IWindowsUpdateCollector
{
    IReadOnlyList<WindowsUpdateEntry> GetUpdates();
}
