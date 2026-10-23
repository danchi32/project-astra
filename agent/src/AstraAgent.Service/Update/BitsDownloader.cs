using System.Runtime.InteropServices;
using Microsoft.Extensions.Logging;

namespace AstraAgent.Service.Update;

/// <summary>Downloads the update package via BITS (the Background Intelligent Transfer Service —
/// the same Windows component Windows Update itself uses).
///
/// The point is <b>network politeness</b>, not fewer bytes. A BITS job at LOW priority rides only
/// the bandwidth nothing else is using and backs off the instant the machine has foreground
/// traffic, so a whole site updating at once can no longer saturate its uplink the way fifty
/// simultaneous blocking HTTP GETs would. It also resumes across a dropped link instead of
/// starting over. Each device still fetches the whole package — cutting a site to a single
/// download is the peer-caching work that comes later; this is the no-regret first step.
///
/// Returns false, changing nothing, whenever BITS can't be used — the service is disabled by
/// policy, the SKU doesn't carry it, the COM class won't activate, or the transfer errors out — so
/// the caller falls straight back to a direct HTTP download. An update must never fail to happen
/// because BITS happens to be unavailable on one machine.</summary>
public static class BitsDownloader
{
    // CLSID_BackgroundCopyManager — the base coclass resolves to the newest BITS the OS has.
    private static readonly Guid ClsidBackgroundCopyManager =
        new("4991D34B-80A1-4291-83B6-3328366B9097");

    // How long to let a single transfer run before giving up and falling back. Matches the direct
    // HTTP download's own timeout; BITS retries transient errors itself within this window.
    private static readonly TimeSpan MaxTransferTime = TimeSpan.FromMinutes(10);

    public static Task<bool> TryDownloadAsync(
        string url, string destPath, string? proxyUrl, ILogger logger, CancellationToken ct)
        // COM + a polling wait: push it off the caller's thread. Task.Run threads are MTA, which is
        // what the BITS interfaces expect regardless of whether the caller is the service worker
        // (already MTA) or the tray (a WinForms STA).
        => Task.Run(() => Download(url, destPath, proxyUrl, logger, ct), ct);

    private static bool Download(
        string url, string destPath, string? proxyUrl, ILogger logger, CancellationToken ct)
    {
        IBackgroundCopyManager? manager = null;
        IBackgroundCopyJob? job = null;
        try
        {
            var type = Type.GetTypeFromCLSID(ClsidBackgroundCopyManager, throwOnError: false);
            if (type is null || Activator.CreateInstance(type) is not IBackgroundCopyManager m)
                return false;
            manager = m;

            manager.CreateJob("ASTRA agent update", BgJobType.Download, out _, out job);
            // LOW: pure background. Yields to any foreground traffic on the machine — the reason
            // a fleet-wide update stops being able to starve a site's link.
            job.SetPriority(BgJobPriority.Low);

            // Honour an explicit corporate proxy when one is configured (the tray carries one);
            // otherwise let BITS use the machine's own WinHTTP/WPAD configuration, which is what a
            // LocalSystem service wants on a locked-down network.
            if (!string.IsNullOrWhiteSpace(proxyUrl)
                && Uri.TryCreate(proxyUrl, UriKind.Absolute, out var proxy))
                job.SetProxySettings(BgJobProxyUsage.Override, proxy.Authority, "<local>");

            // BITS renames the temp file into place on Complete(); a stale destination blocks that.
            try { if (File.Exists(destPath)) File.Delete(destPath); } catch { /* best effort */ }

            job.AddFile(url, destPath);
            job.Resume();

            var deadline = DateTime.UtcNow + MaxTransferTime;
            while (true)
            {
                if (ct.IsCancellationRequested || DateTime.UtcNow > deadline)
                {
                    SafeCancel(job);
                    return false;
                }

                job.GetState(out var state);
                switch (state)
                {
                    case BgJobState.Transferred:
                        job.Complete();
                        return File.Exists(destPath);
                    case BgJobState.Error:
                        logger.LogWarning(
                            "BITS transfer of {Url} entered ERROR state; falling back to direct download.", url);
                        SafeCancel(job);
                        return false;
                    // Queued / Connecting / Transferring / TransientError: keep waiting. BITS
                    // recovers transient errors (a dropped link, a 5xx) on its own until the deadline.
                }

                Thread.Sleep(500);
            }
        }
        catch (Exception ex)
        {
            logger.LogWarning(
                ex, "BITS unavailable for {Url}; falling back to a direct download.", url);
            if (job is not null) SafeCancel(job);
            return false;
        }
        finally
        {
            if (job is not null) Marshal.FinalReleaseComObject(job);
            if (manager is not null) Marshal.FinalReleaseComObject(manager);
        }
    }

    private static void SafeCancel(IBackgroundCopyJob job)
    {
        try { job.Cancel(); } catch { /* the job may already be gone */ }
    }

    // ── Minimal BITS COM interop ─────────────────────────────────────────────────────────────
    // Only the members this downloader calls carry real signatures; the rest are slot placeholders
    // so the vtable lines up. Do NOT call a placeholder — add its real signature first.

    private enum BgJobType { Download = 0, Upload = 1, UploadReply = 2 }

    private enum BgJobPriority { Foreground = 0, High = 1, Normal = 2, Low = 3 }

    private enum BgJobState
    {
        Queued = 0, Connecting = 1, Transferring = 2, Suspended = 3,
        Error = 4, TransientError = 5, Transferred = 6, Acknowledged = 7, Cancelled = 8,
    }

    private enum BgJobProxyUsage { Preconfig = 0, NoProxy = 1, Override = 2, Autodetect = 3 }

    [ComImport, Guid("5CE34C0D-0DC9-4C1F-897C-DAA1B78CEE7C"),
     InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    private interface IBackgroundCopyManager
    {
        void CreateJob(
            [MarshalAs(UnmanagedType.LPWStr)] string displayName,
            BgJobType type,
            out Guid jobId,
            [MarshalAs(UnmanagedType.Interface)] out IBackgroundCopyJob job);
        // Remaining members (GetJob, EnumJobs, GetErrorDescription) unused — omitted intentionally.
    }

    [ComImport, Guid("37668D37-507E-4160-9316-26306D150B12"),
     InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    private interface IBackgroundCopyJob
    {
        void AddFileSet();                                                            // 1 (unused)
        void AddFile(                                                                 // 2
            [MarshalAs(UnmanagedType.LPWStr)] string remoteUrl,
            [MarshalAs(UnmanagedType.LPWStr)] string localName);
        void EnumFiles();                                                             // 3 (unused)
        void Suspend();                                                               // 4 (unused)
        void Resume();                                                                // 5
        void Cancel();                                                                // 6
        void Complete();                                                              // 7
        void GetId();                                                                 // 8 (unused)
        void GetType();                                                               // 9 (unused)
        void GetProgress();                                                           // 10 (unused)
        void GetTimes();                                                              // 11 (unused)
        void GetState(out BgJobState state);                                          // 12
        void GetError();                                                              // 13 (unused)
        void GetOwner();                                                              // 14 (unused)
        void SetDisplayName();                                                        // 15 (unused)
        void GetDisplayName();                                                        // 16 (unused)
        void SetDescription();                                                        // 17 (unused)
        void GetDescription();                                                        // 18 (unused)
        void SetPriority(BgJobPriority priority);                                     // 19
        void GetPriority();                                                           // 20 (unused)
        void SetNotifyFlags();                                                        // 21 (unused)
        void GetNotifyFlags();                                                        // 22 (unused)
        void SetNotifyInterface();                                                    // 23 (unused)
        void GetNotifyInterface();                                                    // 24 (unused)
        void SetMinimumRetryDelay();                                                  // 25 (unused)
        void GetMinimumRetryDelay();                                                  // 26 (unused)
        void SetNoProgressTimeout();                                                  // 27 (unused)
        void GetNoProgressTimeout();                                                  // 28 (unused)
        void GetErrorCount();                                                         // 29 (unused)
        void SetProxySettings(                                                        // 30
            BgJobProxyUsage proxyUsage,
            [MarshalAs(UnmanagedType.LPWStr)] string? proxyList,
            [MarshalAs(UnmanagedType.LPWStr)] string? proxyBypassList);
        // TakeOwnership (31) and later members unused — omitted intentionally.
    }
}
