using AstraAgent.Service.Telemetry.Collectors;
using Xunit;

using HistoryEntry = AstraAgent.Service.Telemetry.Collectors.WindowsUpdateCollector.HistoryEntry;

namespace AstraAgent.Service.Tests;

/// <summary>How an update's real state is worked out.
///
/// The states come from WUA, which needs COM and a real machine, but the two decisions that
/// actually classify an update are pure and are what this covers. They matter because both
/// fail silently: a KB that can't be parsed out of a history title simply looks like an
/// update nobody ever tried to install, which is exactly the "everything is Pending" report
/// that made the portal disagree with the device.</summary>
public class WindowsUpdateStateTests
{
    [Theory]
    // What WUA history actually puts in Title, including the build suffix that follows the KB.
    [InlineData("2026-06 Security Update for Windows 11 (KB5094126) (26200.8655)", "KB5094126")]
    [InlineData("2026-07 .NET Framework Security Update (KB5100998)", "KB5100998")]
    [InlineData("Update for Windows Security platform - KB5007651 (Version 10.0.29628.1000)", "KB5007651")]
    public void KbFromTitle_finds_the_article_id(string title, string expected)
        => Assert.Equal(expected, WindowsUpdateCollector.KbFromTitle(title));

    [Theory]
    // Driver and definition updates often carry no KB at all. Returning null is right —
    // inventing one would attach someone else's history to this update.
    [InlineData("Intel Corporation - Display - 31.0.101.5333")]
    [InlineData("Security Intelligence Update for Microsoft Defender Antivirus")]
    public void KbFromTitle_returns_null_when_there_is_no_kb(string title)
        => Assert.Null(WindowsUpdateCollector.KbFromTitle(title));

    [Fact]
    public void An_update_nobody_has_tried_is_simply_pending()
    {
        var (state, code) = WindowsUpdateCollector.Classify(
            "KB5094126", new Dictionary<string, HistoryEntry>(), rebootRequired: false);

        Assert.Equal(UpdateState.Pending, state);
        Assert.Null(code);
    }

    [Fact]
    public void A_successful_install_with_a_reboot_owed_is_awaiting_restart()
    {
        // The case that started this: the device had installed KB5094126 and KB5100998 and
        // said "Pending restart" on its own Windows Update page, while ASTRA reported them
        // as pending and offered to install them again.
        var history = new Dictionary<string, HistoryEntry>
        {
            ["KB5094126"] = new("2026-06 Security Update (KB5094126)", Succeeded: true, ErrorCode: null),
        };

        var (state, code) = WindowsUpdateCollector.Classify("KB5094126", history, rebootRequired: true);

        Assert.Equal(UpdateState.PendingRestart, state);
        Assert.Null(code);
    }

    [Fact]
    public void A_successful_install_with_no_reboot_owed_is_not_claimed_as_restart_pending()
    {
        // Without the reboot check, an update that installed and was later superseded would
        // be reported as waiting on a restart forever — telling the user to reboot for
        // nothing, repeatedly.
        var history = new Dictionary<string, HistoryEntry>
        {
            ["KB5094126"] = new("2026-06 Security Update (KB5094126)", Succeeded: true, ErrorCode: null),
        };

        var (state, _) = WindowsUpdateCollector.Classify("KB5094126", history, rebootRequired: false);

        Assert.Equal(UpdateState.Pending, state);
    }

    [Fact]
    public void A_failed_install_carries_the_code_windows_reported()
    {
        // 0x80244018 is the device in question: the update server returned 403, so retrying
        // will keep failing. "Failed" alone would send someone to press Retry all week.
        var history = new Dictionary<string, HistoryEntry>
        {
            ["KB5007651"] = new("Windows Security platform - KB5007651", Succeeded: false, ErrorCode: "0x80244018"),
        };

        var (state, code) = WindowsUpdateCollector.Classify("KB5007651", history, rebootRequired: true);

        Assert.Equal(UpdateState.Failed, state);
        Assert.Equal("0x80244018", code);
        // A pending reboot elsewhere on the machine must not turn a failure into a success.
        Assert.NotEqual(UpdateState.PendingRestart, state);
    }
}
