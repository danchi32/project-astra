using System.Net;
using AstraAgent.Service.Workforce;
using Microsoft.Win32;

namespace AstraAgent.Service.Api;

/// <summary>Whether the backend has said this device's organization is inactive (trial ended,
/// past due, suspended, canceled), so the agent should go dormant instead of calling every
/// minute.
///
/// An inactive org's every agent call is refused with 403 and <c>X-Subscription-Status:
/// inactive</c>. Calling on regardless cost the backend thousands of refused requests a day per
/// device for nothing. Dormant, the Service sends one heartbeat an hour as a probe and nothing
/// else, and the Tray stops polling for tasks. The probe is also how the device wakes up: the
/// first Ok beat after the org renews clears the state and everything resumes.
///
/// Set by the HeartbeatWorker, read by the TelemetryWorker in the same process, and mirrored to
/// the registry for the user-session Tray, the same bridge <see cref="ActivityTrackingState"/>
/// uses. The update check is not affected: the backend keeps answering it for inactive orgs so a
/// dormant device can still receive new agent versions.</summary>
public sealed class SubscriptionState
{
    internal const string ValueName = "SubscriptionInactive";
    internal const string HeaderName = "X-Subscription-Status";

    /// <summary>How often a dormant device asks again. Also the longest an org that renews
    /// waits before its agents resume.</summary>
    public static readonly TimeSpan DormantProbeInterval = TimeSpan.FromHours(1);

    private volatile bool _dormant;

    public bool Dormant => _dormant;

    public void Set(bool dormant)
    {
        _dormant = dormant;
        try
        {
            using var baseKey = RegistryKey.OpenBaseKey(RegistryHive.LocalMachine, RegistryView.Registry64);
            using var key = baseKey.CreateSubKey(ActivityTrackingState.KeyPath, writable: true);
            key?.SetValue(ValueName, dormant ? 1 : 0, RegistryValueKind.DWord);
        }
        catch
        {
            // Best-effort: the in-memory flag still quiets this process. A Tray that cannot read
            // the value keeps polling with its own failure backoff, which is the safe failure.
        }
    }

    /// <summary>Read by the Tray. False on any failure or missing value, so a Tray that cannot
    /// tell never stops serving a paying organization.</summary>
    public static bool ReadFromRegistry()
    {
        try
        {
            using var baseKey = RegistryKey.OpenBaseKey(RegistryHive.LocalMachine, RegistryView.Registry64);
            using var key = baseKey.OpenSubKey(ActivityTrackingState.KeyPath, writable: false);
            return key?.GetValue(ValueName) is int i && i != 0;
        }
        catch
        {
            return false;
        }
    }

    /// <summary>True only for the backend's explicit "organization inactive" refusal. Any other
    /// 403 (or any other status) is an ordinary failure and must not put the device to sleep.</summary>
    public static bool IsInactiveResponse(HttpResponseMessage response) =>
        response.StatusCode == HttpStatusCode.Forbidden
        && response.Headers.TryGetValues(HeaderName, out var values)
        && values.Any(v => string.Equals(v.Trim(), "inactive", StringComparison.OrdinalIgnoreCase));
}
