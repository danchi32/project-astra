using Microsoft.Win32;

namespace AstraAgent.Service.Telemetry.Collectors;

/// <summary>Reports Windows updates: what's PENDING (via the Windows Update Agent) and what's
/// already installed (from the servicing registry).
///
/// Pending detection used to be missing entirely — this only read installed hotfixes and
/// hard-coded IsInstalled: true, so the backend never saw an outstanding update. The patch
/// compliance check therefore passed on every device without ever verifying anything, and
/// Fleet Issues could never surface a missing patch.
///
/// The old comment said WUA "requires admin privileges and is deferred". That no longer
/// holds: this collector runs inside the Service, which is SYSTEM, and the same COM API is
/// already used to install updates.</summary>
public sealed class WindowsUpdateCollector(ILogger<WindowsUpdateCollector> logger) : IWindowsUpdateCollector
{
    private const string HotfixKey = @"SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\Packages";

    // Same criteria the installer uses, so the count reported here is exactly what a push
    // would act on. A number that doesn't match what the fix does is worse than no number.
    private const string PendingCriteria = "IsInstalled=0 and Type='Software' and IsHidden=0";

    public IReadOnlyList<WindowsUpdateEntry> GetUpdates()
    {
        var result = new List<WindowsUpdateEntry>();
        result.AddRange(GetPending());
        result.AddRange(GetInstalled(exclude: result.Select(r => r.KbArticleId)));
        return result;
    }

    private List<WindowsUpdateEntry> GetPending()
    {
        var pending = new List<WindowsUpdateEntry>();
        var sessionType = Type.GetTypeFromProgID("Microsoft.Update.Session");
        if (sessionType is null)
        {
            logger.LogWarning("Windows Update Agent COM is unavailable; pending updates not collected");
            return pending;
        }

        var coms = new List<object>();
        try
        {
            dynamic session = Activator.CreateInstance(sessionType)!;
            coms.Add(session);
            dynamic searcher = session.CreateUpdateSearcher();
            coms.Add(searcher);

            // Search the LOCAL cache, not Microsoft's servers. An online search takes tens of
            // seconds and puts real load on both the device and Windows Update; doing that on
            // every inventory pass across a large fleet is not acceptable. Windows refreshes
            // this cache on its own schedule, so the answer is current enough for reporting —
            // and the install action still performs a full online search when it actually runs.
            try { searcher.Online = false; } catch { /* older WUA: leave the default */ }

            dynamic searchResult = searcher.Search(PendingCriteria);
            coms.Add(searchResult);

            var count = (int)searchResult.Updates.Count;
            for (var i = 0; i < count && pending.Count < 100; i++)
            {
                dynamic u = searchResult.Updates.Item(i);
                pending.Add(new WindowsUpdateEntry(
                    KbArticleId: FirstKbId(u),
                    Title: SafeTitle(u),
                    IsInstalled: false,
                    InstalledOn: null));
            }
            logger.LogInformation("Windows Update: {Count} pending update(s) found", pending.Count);
        }
        catch (Exception ex)
        {
            // Never fail the whole telemetry push over this: a device with a broken WU stack
            // should still report CPU, disk and events.
            logger.LogWarning(ex, "Pending Windows Update collection failed");
        }
        finally
        {
            for (var i = coms.Count - 1; i >= 0; i--)
            {
                try { System.Runtime.InteropServices.Marshal.FinalReleaseComObject(coms[i]); }
                catch { /* best effort */ }
            }
        }
        return pending;
    }

    private static string FirstKbId(dynamic update)
    {
        // An update usually carries one KB id; fall back to the update's GUID so the row is
        // still identifiable when it carries none (some driver/definition updates don't).
        try
        {
            var ids = update.KBArticleIDs;
            if ((int)ids.Count > 0) return "KB" + (string)ids.Item(0);
        }
        catch { /* fall through */ }
        try { return ((string)update.Identity.UpdateID)[..8].ToUpperInvariant(); }
        catch { return "UNKNOWN"; }
    }

    private static string SafeTitle(dynamic update)
    {
        try { return ((string)update.Title) is { Length: > 0 } t ? t : "Windows update"; }
        catch { return "Windows update"; }
    }

    private List<WindowsUpdateEntry> GetInstalled(IEnumerable<string> exclude)
    {
        // Installed history comes from the servicing registry rather than WUA: it is instant,
        // needs no COM, and an IsInstalled=1 WUA search returns thousands of rows.
        var installed = new List<WindowsUpdateEntry>();
        var skip = new HashSet<string>(exclude, StringComparer.OrdinalIgnoreCase);
        try
        {
            using var key = Registry.LocalMachine.OpenSubKey(HotfixKey);
            if (key is null) return installed;

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
                var kb = new string(kbRaw.TakeWhile(char.IsLetterOrDigit).ToArray());

                if (!skip.Add(kb)) continue;   // already listed as pending, or a duplicate

                installed.Add(new WindowsUpdateEntry(kb, subKeyName, IsInstalled: true, InstalledOn: null));
                if (installed.Count >= 100) break;
            }
        }
        catch (Exception ex)
        {
            logger.LogWarning(ex, "Installed Windows Update collection failed");
        }
        return installed;
    }
}
