using Microsoft.Win32;

namespace AstraAgent.Service.Workforce;

/// <summary>Shared truth for "is Tracker activity collection on for this org".
///
/// Written by the HeartbeatWorker from the backend's answer on each beat; read by the
/// TelemetryWorker (same process) to decide whether to collect, and mirrored to a registry
/// value the user-session Tray reads so it can show "Activity tracking: ON". The Service and
/// the Tray are different processes and share no memory, so the registry is the bridge — the
/// same mechanism RemoteSupportAgent uses to read the relay agent's own key.
///
/// The server decides; the agent only reflects. That is what keeps tracking from ever being
/// covert: collection is gated on this, and whenever it is on the Tray says so.</summary>
public sealed class ActivityTrackingState
{
    internal const string KeyPath = @"SOFTWARE\Astra";
    internal const string ValueName = "ActivityTracking";
    internal const string UrlModeValueName = "ActivityUrlMode";

    private volatile bool _enabled;

    /// <summary>Whether collection is on, for the in-process TelemetryWorker.</summary>
    public bool Enabled => _enabled;

    /// <summary>Record the backend's answer: hold tracking in memory for this process and
    /// mirror both tracking and the URL mode to the registry for the Tray.</summary>
    public void Set(bool enabled, string urlMode = "domain")
    {
        _enabled = enabled;
        WriteRegistry(enabled, urlMode == "path" ? "path" : "domain");
    }

    private static void WriteRegistry(bool enabled, string urlMode)
    {
        try
        {
            using var baseKey = RegistryKey.OpenBaseKey(RegistryHive.LocalMachine, RegistryView.Registry64);
            using var key = baseKey.CreateSubKey(KeyPath, writable: true);
            key?.SetValue(ValueName, enabled ? 1 : 0, RegistryValueKind.DWord);
            key?.SetValue(UrlModeValueName, urlMode, RegistryValueKind.String);
        }
        catch
        {
            // Best-effort. The in-memory flag still gates collection; a Tray that cannot read
            // the value just shows no indicator, which is the safe failure — it never claims
            // tracking is on when it cannot confirm it.
        }
    }

    /// <summary>Read by the Tray (a user-session process) to decide whether to show the
    /// indicator. False on any failure or a missing value — the Tray must never claim
    /// tracking is on when it cannot confirm it.</summary>
    public static bool ReadFromRegistry()
    {
        try
        {
            using var baseKey = RegistryKey.OpenBaseKey(RegistryHive.LocalMachine, RegistryView.Registry64);
            using var key = baseKey.OpenSubKey(KeyPath, writable: false);
            return key?.GetValue(ValueName) is int i && i != 0;
        }
        catch
        {
            return false;
        }
    }

    /// <summary>The URL mode the Tray should capture at — "domain" or "path". Defaults to the
    /// privacy-preserving "domain" on any failure or missing value.</summary>
    public static string ReadUrlModeFromRegistry()
    {
        try
        {
            using var baseKey = RegistryKey.OpenBaseKey(RegistryHive.LocalMachine, RegistryView.Registry64);
            using var key = baseKey.OpenSubKey(KeyPath, writable: false);
            return key?.GetValue(UrlModeValueName) as string == "path" ? "path" : "domain";
        }
        catch
        {
            return "domain";
        }
    }
}
