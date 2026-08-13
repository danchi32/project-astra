using System;
using Microsoft.Win32;

namespace AstraAgent.Service.Remediation;

/// <summary>Turns USB mass storage on or off for the whole machine.
///
/// Windows loads a specific driver, USBSTOR, for pen drives and portable disks, and its
/// Start value is the switch: 3 means "load on demand" (the normal state) and 4 means
/// "disabled". Nothing else keys off this — keyboards, mice, webcams and phones-as-cameras
/// load their own drivers and are untouched, which is exactly what "storage only" means.
///
/// The change is to one HKLM value and takes hold when a device is next connected; a drive
/// already plugged in keeps working until it is unplugged. This is the long-standing method
/// Windows itself documents, chosen over a Group Policy edit because it is one value to set
/// and one value to read back, so the agent can confirm what it did.</summary>
public static class UsbStorageManager
{
    private const string KeyPath = @"SYSTEM\CurrentControlSet\Services\USBSTOR";
    private const string ValueName = "Start";
    private const int Enabled = 3;
    private const int Disabled = 4;

    /// <summary>The current state, for telemetry: true = blocked, false = allowed, null =
    /// could not be read. Null rather than a guess so a transient read failure never reports
    /// a blocked device as allowed — the backend leaves the last known value alone on null.</summary>
    public static bool? IsBlocked()
    {
        try
        {
            using var key = Registry.LocalMachine.OpenSubKey(KeyPath, writable: false);
            if (key?.GetValue(ValueName) is int start)
                return start == Disabled;
            return null;
        }
        catch
        {
            return null;
        }
    }

    public static (bool Success, string Output) SetBlocked(bool blocked)
    {
        var target = blocked ? Disabled : Enabled;
        try
        {
            using var key = Registry.LocalMachine.OpenSubKey(KeyPath, writable: true);
            if (key is null)
                return (false,
                    "The USB storage driver key is not present on this machine, so there is "
                    + "nothing to switch. USB storage may already be removed by policy.");

            key.SetValue(ValueName, target, RegistryValueKind.DWord);

            // Read it back: a write that did not take is worse than an error, because the
            // administrator would believe the port was closed while it stayed open.
            var readBack = key.GetValue(ValueName);
            if (readBack is not int actual || actual != target)
                return (false,
                    $"Tried to {(blocked ? "block" : "allow")} USB storage but the setting did "
                    + "not stick — it may be enforced by a Group Policy that overrides it.");

            return blocked
                ? (true, "USB storage is now blocked. Pen drives and portable disks will not "
                         + "work from the next time one is connected; a drive plugged in right "
                         + "now keeps working until it is removed. Keyboards, mice and other "
                         + "USB devices are unaffected.")
                : (true, "USB storage is allowed again. Pen drives and portable disks will work "
                         + "from the next time one is connected.");
        }
        catch (UnauthorizedAccessException)
        {
            return (false, "Changing USB storage needs administrator rights the service did not "
                           + "have for this key.");
        }
        catch (Exception ex)
        {
            return (false, $"Could not change USB storage: {ex.Message}");
        }
    }
}
