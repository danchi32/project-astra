namespace AstraAgent.Service.Telemetry.Collectors;

/// <summary>One installed application.
///
/// <paramref name="Scope"/> is "machine" for an install every user gets (HKLM) and "user" for
/// one that lives in a single person's profile (HKCU of that user). Per-user installs are the
/// ones that matter most for shadow-IT questions — ChatGPT, Claude, Cursor, Zoom, Ollama all
/// install into the user's own profile by default — and were invisible before this field.
/// <paramref name="UserName"/> is the profile's account (DOMAIN\name) for a "user" app and
/// null for a "machine" one.</summary>
public sealed record InstalledApp(
    string Name,
    string? Version,
    string? Publisher,
    string? InstallDate,
    string Scope = InstalledApp.MachineScope,
    string? UserName = null)
{
    public const string MachineScope = "machine";
    public const string UserScope = "user";
}

public interface IInstalledAppsCollector
{
    IReadOnlyList<InstalledApp> GetInstalledApps();
}
