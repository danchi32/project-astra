using Microsoft.Win32;

namespace AstraAgent.Service.Telemetry.Collectors;

public sealed class InstalledAppsCollector(ILogger<InstalledAppsCollector> logger) : IInstalledAppsCollector
{
    private static readonly string[] UninstallKeys =
    [
        @"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
        @"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
    ];

    public IReadOnlyList<InstalledApp> GetInstalledApps()
    {
        var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        var result = new List<InstalledApp>();

        foreach (var keyPath in UninstallKeys)
        {
            try
            {
                using var root = Registry.LocalMachine.OpenSubKey(keyPath);
                if (root is null) continue;

                foreach (var subKeyName in root.GetSubKeyNames())
                {
                    using var sub = root.OpenSubKey(subKeyName);
                    if (sub is null) continue;

                    var name = sub.GetValue("DisplayName") as string;
                    if (string.IsNullOrWhiteSpace(name)) continue;
                    if (sub.GetValue("SystemComponent") is int sc && sc == 1) continue;
                    if (!seen.Add(name)) continue;

                    result.Add(new InstalledApp(
                        name.Trim()[..Math.Min(name.Length, 300)],
                        (sub.GetValue("DisplayVersion") as string)?.Trim(),
                        (sub.GetValue("Publisher") as string)?.Trim(),
                        (sub.GetValue("InstallDate") as string)?.Trim()));
                }
            }
            catch (Exception ex)
            {
                logger.LogWarning(ex, "Could not read registry key {Key}", keyPath);
            }
        }

        return result.OrderBy(a => a.Name).ToList();
    }
}
