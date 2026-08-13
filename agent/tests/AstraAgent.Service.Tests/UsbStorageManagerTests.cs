using AstraAgent.Service.Remediation;
using TrayRemediation = AstraAgent.Tray.Remediation.RemediationExecutor;
using Xunit;

namespace AstraAgent.Service.Tests;

/// <summary>USB storage control, as far as it can be checked off a real machine.
///
/// SetBlocked writes one value under HKLM and reads it back, so exercising it here would
/// change whether this very machine accepts pen drives — not something a test may do. What
/// is verified instead is the boundary that does not need the registry: the elevated service
/// accepts exactly these two actions and still refuses everything else. The registry write
/// itself is proven on a device, like the uninstall and the time-zone change beside it.</summary>
public class UsbStorageManagerTests
{
    [Theory]
    [InlineData("block_usb_storage")]
    [InlineData("unblock_usb_storage")]
    public void The_elevated_service_accepts_both_halves_of_the_pair(string actionId)
    {
        Assert.Contains(actionId, SystemRemediationExecutor.SupportedActions);
    }

    [Fact]
    public void Neither_half_is_offered_to_the_user_session_tray()
    {
        // These need administrator rights and belong to the elevated service alone. If one
        // ever appeared in the tray's list it would be dispatched to a process that cannot
        // perform it, and fail on every device.
        Assert.DoesNotContain("block_usb_storage", TrayRemediation.SupportedActions);
        Assert.DoesNotContain("unblock_usb_storage", TrayRemediation.SupportedActions);
    }
}
