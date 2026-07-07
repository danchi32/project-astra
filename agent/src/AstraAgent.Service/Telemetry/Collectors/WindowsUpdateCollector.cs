using Microsoft.Win32;

namespace AstraAgent.Service.Telemetry.Collectors;

/// <summary>Reads installed hotfixes from the registry (Win32_QuickFixEngineering equivalent).
/// The full WUA COM API requires admin privileges and is deferred to a future phase.</summary>
public sealed class WindowsUpdateCollector(ILogger<WindowsUpdateCollector> logger) : IWindowsUpdateCollector
{
    private const string HotfixKey = @"SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\Packages";

    public IReadOnlyList<WindowsUpdateEntry> GetUpdates()
    {
        var result = new List<WindowsUpdateEntry>();
        try
        {
            // Read recently installed KBs from the registry hotfix path.
            using var key = Registry.LocalMachine.OpenSubKey(HotfixKey);
            if (key is null) return result;

            foreach (var subKeyName in key.GetSubKeyNames())
            {
                if (!subKeyName.Contains("KB", StringComparison.OrdinalIgnoreCase)) continue;
                using var sub = key.OpenSubKey(subKeyName);
                if (sub is null) continue;

                var state = sub.GetValue("CurrentState") as int?;
                // 112 = Installed
                if (state != 112) continue;

                var kbStart = subKeyName.IndexOf("KB", StringComparison.OrdinalIgnoreCase);
                var kbRaw = subKeyName[kbStart..];
                var kb = new string(kbRaw.TakeWhile(c => char.IsLetterOrDigit(c)).ToArray());

                if (result.Any(r => r.KbArticleId.Equals(kb, StringComparison.OrdinalIgnoreCase)))
                    continue;

                result.Add(new WindowsUpdateEntry(kb, subKeyName, IsInstalled: true, InstalledOn: null));

                if (result.Count >= 100) break;
            }
        }
        catch (Exception ex)
        {
            logger.LogWarning(ex, "Windows Update collection failed");
        }
        return result;
    }
}
