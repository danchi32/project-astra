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
        result.AddRange(GetOutstanding());
        result.AddRange(GetInstalled(exclude: result.Select(r => r.KbArticleId)));
        return result;
    }

    /// <summary>Everything not yet in effect, each with the reason it isn't — which is what
    /// the Windows Update page shows and what the portal has to match. "Pending", "Pending
    /// restart" and "Download error - 0x80244018" call for three different responses, and
    /// only one of them is "install it again".</summary>
    private List<WindowsUpdateEntry> GetOutstanding()
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

            // Windows' own record of what it last tried and how it went. This is where the
            // failure codes live: a search alone reports an update as simply "not installed"
            // whether nobody pushed it or it has been failing to download for a week.
            // Explicitly typed: passing a dynamic argument makes the CALL dynamic, so `var`
            // here would infer dynamic and every use of the dictionary below would fail to
            // deconstruct at compile time.
            Dictionary<string, HistoryEntry> history = ReadHistory(searcher);
            var rebootRequired = RebootIsPending();

            // Search the LOCAL cache, not Microsoft's servers. An online search takes tens of
            // seconds and puts real load on both the device and Windows Update; doing that on
            // every inventory pass across a large fleet is not acceptable. Windows refreshes
            // this cache on its own schedule, so the answer is current enough for reporting —
            // and the install action still performs a full online search when it actually runs.
            try { searcher.Online = false; } catch { /* older WUA: leave the default */ }

            dynamic searchResult = searcher.Search(PendingCriteria);
            coms.Add(searchResult);

            var count = (int)searchResult.Updates.Count;
            var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            for (var i = 0; i < count && pending.Count < 100; i++)
            {
                dynamic u = searchResult.Updates.Item(i);
                // Typed for the same reason as `history` above: FirstKbId takes a dynamic, so
                // its result is dynamic and would poison Classify's tuple deconstruction.
                string kb = FirstKbId(u);
                seen.Add(kb);
                var (state, code) = Classify(kb, history, rebootRequired);
                pending.Add(new WindowsUpdateEntry(
                    KbArticleId: kb,
                    Title: SafeTitle(u),
                    IsInstalled: state == UpdateState.PendingRestart,
                    InstalledOn: null,
                    State: state,
                    ErrorCode: code));
            }

            // An update that installed and is waiting on a reboot may already have dropped
            // out of the IsInstalled=0 search, but it is still not in effect and the device
            // is still unpatched until it restarts. Reporting it as plain "installed" would
            // hide the one thing anybody needs to do about it.
            if (rebootRequired)
            {
                foreach (var (kb, entry) in history)
                {
                    if (pending.Count >= 100) break;
                    if (!entry.Succeeded || !seen.Add(kb)) continue;
                    pending.Add(new WindowsUpdateEntry(
                        KbArticleId: kb, Title: entry.Title, IsInstalled: true,
                        InstalledOn: null, State: UpdateState.PendingRestart));
                }
            }

            logger.LogInformation(
                "Windows Update: {Pending} pending, {Restart} awaiting restart, {Failed} failed",
                pending.Count(p => p.State == UpdateState.Pending),
                pending.Count(p => p.State == UpdateState.PendingRestart),
                pending.Count(p => p.State == UpdateState.Failed));
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

    internal readonly record struct HistoryEntry(string Title, bool Succeeded, string? ErrorCode);

    /// <summary>The most recent install attempt per KB, from WUA's own history.</summary>
    private Dictionary<string, HistoryEntry> ReadHistory(dynamic searcher)
    {
        // Newest first, so the first entry seen for a KB is its latest attempt. Bounded:
        // a machine can carry thousands of history rows and only the recent ones describe
        // the state it is in now.
        var byKb = new Dictionary<string, HistoryEntry>(StringComparer.OrdinalIgnoreCase);
        try
        {
            var total = (int)searcher.GetTotalHistoryCount();
            if (total <= 0) return byKb;

            dynamic entries = searcher.QueryHistory(0, Math.Min(total, 200));
            var count = (int)entries.Count;
            for (var i = 0; i < count; i++)
            {
                dynamic h = entries.Item(i);

                // Operation 1 = installation. An uninstall says nothing about whether the
                // update is currently outstanding.
                int operation;
                try { operation = (int)h.Operation; } catch { operation = 1; }
                if (operation != 1) continue;

                var title = SafeHistoryTitle(h);
                var kb = KbFromTitle(title);
                if (kb is null || byKb.ContainsKey(kb)) continue;

                // OperationResultCode: 2 = Succeeded, 3 = SucceededWithErrors, 4 = Failed,
                // 5 = Aborted. 0/1 mean it never finished, which is not a verdict either way.
                int resultCode;
                try { resultCode = (int)h.ResultCode; } catch { continue; }
                if (resultCode is < 2 or > 5) continue;

                var succeeded = resultCode is 2 or 3;
                string? code = null;
                if (!succeeded)
                {
                    try { code = $"0x{(uint)(int)h.HResult:X8}"; } catch { /* leave unset */ }
                }
                byKb[kb] = new HistoryEntry(title, succeeded, code);
            }
        }
        catch (Exception ex)
        {
            // Without history every outstanding update simply reads as "pending", which is
            // what the previous version always reported — degraded, not broken.
            logger.LogWarning(ex, "Windows Update history unavailable; states will be coarse");
        }
        return byKb;
    }

    internal static (string State, string? ErrorCode) Classify(
        string kb, Dictionary<string, HistoryEntry> history, bool rebootRequired)
    {
        if (!history.TryGetValue(kb, out var entry))
            return (UpdateState.Pending, null);

        // Installed but still listed as outstanding, with a reboot owed: it is done and the
        // restart is all that's left. Without the reboot check this would claim
        // "pending_restart" for an update that succeeded and was then superseded.
        if (entry.Succeeded)
            return rebootRequired ? (UpdateState.PendingRestart, null) : (UpdateState.Pending, null);

        return (UpdateState.Failed, entry.ErrorCode);
    }

    /// <summary>Whether the machine owes a restart before pending updates take effect.</summary>
    private bool RebootIsPending()
    {
        try
        {
            var t = Type.GetTypeFromProgID("Microsoft.Update.SystemInfo");
            if (t is not null)
            {
                dynamic info = Activator.CreateInstance(t)!;
                try { return (bool)info.RebootRequired; }
                finally { try { System.Runtime.InteropServices.Marshal.FinalReleaseComObject(info); } catch { } }
            }
        }
        catch (Exception ex)
        {
            logger.LogWarning(ex, "Could not read RebootRequired from WUA; falling back to the registry");
        }

        // Servicing sets this key and WUA does not always agree with it immediately, so it
        // is a fallback rather than the primary source.
        try
        {
            using var key = Registry.LocalMachine.OpenSubKey(
                @"SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired");
            return key is not null;
        }
        catch { return false; }
    }

    internal static string? KbFromTitle(string title)
    {
        // History rows have no KBArticleIDs collection; the KB lives in the title, as in
        // "2026-06 Security Update for Windows 11 (KB5094126) (26200.8655)".
        var i = title.IndexOf("KB", StringComparison.OrdinalIgnoreCase);
        if (i < 0) return null;
        var digits = new string(title[(i + 2)..].TakeWhile(char.IsDigit).ToArray());
        return digits.Length == 0 ? null : "KB" + digits;
    }

    private static string SafeHistoryTitle(dynamic entry)
    {
        try { return ((string)entry.Title) is { Length: > 0 } t ? t : "Windows update"; }
        catch { return "Windows update"; }
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

                installed.Add(new WindowsUpdateEntry(
                    kb, subKeyName, IsInstalled: true, InstalledOn: null,
                    State: UpdateState.Installed));
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
