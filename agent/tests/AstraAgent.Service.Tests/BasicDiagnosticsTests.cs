using AstraAgent.Service.Remediation;
using Xunit;

namespace AstraAgent.Service.Tests;

/// <summary>The first-line diagnostics: sound, DHCP, hardware rescan, system file check.
///
/// Only the decisions are testable here — the effects stop services, drop the network and
/// take half an hour. What is worth holding is the reading of SFC's report, because SFC
/// exits 0 whether it found nothing, repaired everything, or gave up on a file. If the
/// wording match ever drifts, a machine with unrepairable damage gets reported to the user
/// as healthy, and nobody goes to look at it.</summary>
public class BasicDiagnosticsTests
{
    [Fact]
    public void A_clean_scan_is_a_success_and_says_the_fault_is_elsewhere()
    {
        var (ok, output) = BasicDiagnostics.InterpretSfc(
            "Windows Resource Protection did not find any integrity violations.");

        Assert.True(ok);
        Assert.Contains("no damage", output);
    }

    [Fact]
    public void A_repaired_scan_is_a_success_and_asks_for_a_restart()
    {
        var (ok, output) = BasicDiagnostics.InterpretSfc(
            "Windows Resource Protection found corrupt files and successfully repaired them. "
            + "Details are included in the CBS.Log.");

        Assert.True(ok);
        Assert.Contains("restart", output);
    }

    [Fact]
    public void Damage_it_could_not_repair_is_never_reported_as_a_success()
    {
        // The ending that matters: SFC still exits 0 here.
        var (ok, output) = BasicDiagnostics.InterpretSfc(
            "Windows Resource Protection found corrupt files but was unable to fix some of them.");

        Assert.False(ok);
        Assert.Contains("technician", output);
    }

    [Fact]
    public void A_blocked_scan_says_what_to_wait_for_rather_than_failing_blankly()
    {
        var (ok, output) = BasicDiagnostics.InterpretSfc(
            "Windows Resource Protection could not perform the requested operation.");

        Assert.False(ok);
        Assert.Contains("Windows Update", output);
    }

    [Fact]
    public void An_unrecognised_ending_is_not_claimed_as_a_verification()
    {
        var (ok, output) = BasicDiagnostics.InterpretSfc("something nobody has seen before");

        Assert.False(ok);
        Assert.Contains("does not recognise", output);
    }

    [Fact]
    public void The_utf16_nul_bytes_sfc_emits_do_not_break_the_match()
    {
        // What redirecting sfc.exe's UTF-16 output actually looks like as bytes. Without the
        // strip, every real machine falls through to the "unrecognised" branch — and does so
        // silently, because the text still reads correctly in a log.
        var asRedirected = string.Join(
            "\0", "Windows Resource Protection did not find any integrity violations.".ToCharArray());

        var (ok, output) = BasicDiagnostics.InterpretSfc(asRedirected);

        Assert.True(ok);
        Assert.Contains("no damage", output);
    }

    [Theory]
    [InlineData("   IPv4 Address. . . . . . . . . . . : 192.168.1.42", "192.168.1.42")]
    [InlineData("   IPv4 Address. . . . . . . . . . . : 10.0.0.7(Preferred)", "10.0.0.7(Preferred)")]
    public void The_new_address_is_pulled_out_of_ipconfigs_output(string line, string expected)
    {
        Assert.Equal(expected, BasicDiagnostics.FirstIPv4($"Windows IP Configuration\n{line}\n"));
    }

    [Fact]
    public void An_output_with_no_address_costs_nothing()
    {
        // The address only enriches the message, so a failed parse must not fail the action.
        Assert.Null(BasicDiagnostics.FirstIPv4("Windows IP Configuration\n\n"));
        Assert.Null(BasicDiagnostics.FirstIPv4(null));
    }

    [Fact]
    public void The_four_diagnostics_are_all_in_the_elevated_allowlist()
    {
        // The backend routes these to the system context; an id missing here is refused on
        // the device after an admin has already approved it.
        foreach (var id in new[]
                 { "restart_audio", "renew_ip_address", "rescan_devices", "repair_system_files" })
            Assert.Contains(id, SystemRemediationExecutor.SupportedActions);
    }

    [Fact]
    public void None_of_them_leak_into_the_user_session_allowlist()
    {
        // All four need elevation. If one were also in the Tray's list it would be claimed by
        // whichever process polled first, and the unprivileged one would fail.
        foreach (var id in new[]
                 { "restart_audio", "renew_ip_address", "rescan_devices", "repair_system_files" })
            Assert.DoesNotContain(id, AstraAgent.Tray.Remediation.RemediationExecutor.SupportedActions);
    }
}
