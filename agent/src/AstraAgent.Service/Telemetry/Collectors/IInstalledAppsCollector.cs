namespace AstraAgent.Service.Telemetry.Collectors;

public sealed record InstalledApp(string Name, string? Version, string? Publisher, string? InstallDate);

public interface IInstalledAppsCollector
{
    IReadOnlyList<InstalledApp> GetInstalledApps();
}
