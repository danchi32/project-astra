using System.Security.Principal;
using System.Text.RegularExpressions;
using Microsoft.Win32;

namespace AstraAgent.Service.Telemetry.Collectors;

public sealed partial class InstalledAppsCollector(ILogger<InstalledAppsCollector> logger) : IInstalledAppsCollector
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
            ReadUninstallKey(Registry.LocalMachine, keyPath, InstalledApp.MachineScope, null, seen, result);

        // Per-user installs. The service runs as LocalSystem, whose own HKCU is not anyone's —
        // so each signed-in person's hive is read where Windows keeps it loaded, under
        // HKEY_USERS\<their SID>. Only hives that are ALREADY loaded are read: loading a
        // signed-out user's NTUSER.DAT would lock the file and can stop that person signing in.
        // The cost is that a signed-out user's per-user apps are reported the next time they
        // sign in, which is when they can run them anyway.
        string[] sids;
        try
        {
            sids = Registry.Users.GetSubKeyNames();
        }
        catch (Exception ex)
        {
            logger.LogWarning(ex, "Could not enumerate loaded user hives");
            sids = [];
        }

        foreach (var sid in sids.Where(IsUserHive))
        {
            var userName = ResolveAccount(sid);
            foreach (var keyPath in UninstallKeys)
                ReadUninstallKey(Registry.Users, $@"{sid}\{keyPath}", InstalledApp.UserScope, userName, seen, result);
        }

        return result.OrderBy(a => a.Name).ThenBy(a => a.UserName).ToList();
    }

    private void ReadUninstallKey(
        RegistryKey hive, string keyPath, string scope, string? userName,
        HashSet<string> seen, List<InstalledApp> result)
    {
        try
        {
            using var root = hive.OpenSubKey(keyPath);
            if (root is null) return;

            foreach (var subKeyName in root.GetSubKeyNames())
            {
                using var sub = root.OpenSubKey(subKeyName);
                if (sub is null) continue;

                var name = sub.GetValue("DisplayName") as string;
                if (string.IsNullOrWhiteSpace(name)) continue;
                if (sub.GetValue("SystemComponent") is int sc && sc == 1) continue;
                // Dedupe per owner, not globally: the same app installed for two people is two
                // installs, and an app that is both machine-wide and per-user is reported both
                // ways because uninstalling one leaves the other.
                if (!seen.Add($"{scope}|{userName}|{name}")) continue;

                var trimmed = name.Trim();
                result.Add(new InstalledApp(
                    trimmed[..Math.Min(trimmed.Length, 300)],
                    (sub.GetValue("DisplayVersion") as string)?.Trim(),
                    (sub.GetValue("Publisher") as string)?.Trim(),
                    (sub.GetValue("InstallDate") as string)?.Trim(),
                    scope,
                    userName));
            }
        }
        catch (Exception ex)
        {
            logger.LogWarning(ex, "Could not read registry key {Key}", keyPath);
        }
    }

    /// <summary>True for the HKEY_USERS subkey of a real person's profile.
    ///
    /// Local and domain/Entra accounts are S-1-5-21-…; Entra-only (Azure AD) accounts are
    /// S-1-12-1-…. Everything else under HKEY_USERS is a service or built-in account
    /// (.DEFAULT, S-1-5-18/19/20) or the user's "_Classes" companion hive, which holds file
    /// associations, not installs.</summary>
    internal static bool IsUserHive(string keyName) => UserSid().IsMatch(keyName);

    [GeneratedRegex(@"^S-1-(5-21|12-1)(-\d+)+$", RegexOptions.CultureInvariant)]
    private static partial Regex UserSid();

    private string? ResolveAccount(string sid)
    {
        try
        {
            return new SecurityIdentifier(sid).Translate(typeof(NTAccount)).Value;
        }
        catch (Exception ex)
        {
            // An orphaned or offline-domain SID still identifies one person's profile; keep the
            // SID rather than drop their apps.
            logger.LogDebug(ex, "Could not resolve {Sid} to an account name", sid);
            return sid;
        }
    }
}
