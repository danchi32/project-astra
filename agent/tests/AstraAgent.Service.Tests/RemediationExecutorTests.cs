using System.Threading;
using System.Threading.Tasks;
using AstraAgent.Tray.Remediation;
using Xunit;

namespace AstraAgent.Service.Tests;

public class RemediationExecutorTests
{
    [Fact]
    public async Task UnknownAction_IsRefused()
    {
        var executor = new RemediationExecutor();
        var (success, output) = await executor.ExecuteAsync("delete_everything", null, CancellationToken.None);
        Assert.False(success);
        Assert.Contains("not supported", output);
    }

    // All of these ARE implemented now — in the elevated service, which is the point. The
    // Tray runs in the user's session and must still refuse them, so a misrouted task fails
    // closed rather than being half-attempted without the privileges it needs.
    [Theory]
    [InlineData("office_repair")]
    [InlineData("restart_service")]
    [InlineData("network_reset")]
    [InlineData("restart_network_adapter")]
    [InlineData("reset_windows_update_components")]
    [InlineData("registry_fix")]      // removed from the catalogue entirely; still refused here
    public async Task ElevatedOrUnhandledActions_AreRefused(string actionId)
    {
        var executor = new RemediationExecutor();
        var (success, _) = await executor.ExecuteAsync(actionId, null, CancellationToken.None);
        Assert.False(success);
    }

    [Fact]
    public void SupportedActions_AreExactlyTheUserSessionSafeSet()
    {
        // Locks the agent's independent allowlist (defense in depth): it must never run
        // anything outside this exact set, no matter what the backend sends.
        Assert.Equal(
            new[]
            {
                // add_network_printer runs here rather than in the elevated service on
                // purpose: a printer connection belongs to the signed-in person's profile,
                // and one attached by LocalSystem would report success to a printer only
                // LocalSystem can see.
                "add_network_printer",
                "clear_browser_cache", "clear_temp", "create_outlook_rule", "flush_dns",
                "restart_application", "restart_chrome", "restart_edge", "restart_explorer",
                "restart_outlook", "restart_teams", "restart_zoom",
            },
            System.Linq.Enumerable.OrderBy(RemediationExecutor.SupportedActions, x => x).ToArray());
    }

    [Fact]
    public async Task CreateOutlookRule_RequiresBothParams()
    {
        var executor = new RemediationExecutor();
        var (ok, msg) = await executor.ExecuteAsync(
            "create_outlook_rule",
            new System.Collections.Generic.Dictionary<string, string> { ["folder_name"] = "Danish" },
            CancellationToken.None);
        Assert.False(ok);
        Assert.Contains("sender", msg, System.StringComparison.OrdinalIgnoreCase);
    }

    // ---- Did the clearing actually clear anything? --------------------------------
    //
    // The deleting itself needs a real profile on a real machine, so the judgement lives in
    // one pure function and these tests hold that. It is the part that was wrong in the
    // field: a user asked for their Chrome cache to be cleared, Chrome was open, every
    // delete failed, and the agent still answered "fixed".

    [Fact]
    public void Everything_locked_by_an_open_browser_is_a_failure_not_a_fix()
    {
        var (ok, msg) = RemediationExecutor.ClearVerdict(
            "browser cache", "", deleted: 0, lockedOut: 812, freedBytes: 0,
            foundAnything: true, blockedBy: "Google Chrome");

        Assert.False(ok);
        // Naming the app is what makes the message actionable rather than a shrug.
        Assert.Contains("Google Chrome", msg);
        Assert.Contains("Close it", msg);
    }

    [Fact]
    public void A_partial_clear_still_succeeds_but_says_what_was_left()
    {
        var (ok, msg) = RemediationExecutor.ClearVerdict(
            "browser cache", "", deleted: 900, lockedOut: 12, freedBytes: 300L * 1024 * 1024,
            foundAnything: true, blockedBy: "Google Chrome");

        Assert.True(ok);
        Assert.Contains("300 MB", msg);
        Assert.Contains("12 file(s) were locked", msg);
    }

    [Fact]
    public void Nothing_to_clear_is_a_success_unlike_being_unable_to_clear()
    {
        var (ok, msg) = RemediationExecutor.ClearVerdict(
            "browser cache", "", deleted: 0, lockedOut: 0, freedBytes: 0,
            foundAnything: false, blockedBy: "");

        Assert.True(ok);
        Assert.Contains("No browser cache was found", msg);
    }

    [Fact]
    public void An_already_empty_cache_is_a_success()
    {
        // Found the folders, nothing inside, nothing locked: there was genuinely no work.
        var (ok, _) = RemediationExecutor.ClearVerdict(
            "browser cache", "", deleted: 0, lockedOut: 0, freedBytes: 0,
            foundAnything: true, blockedBy: "");

        Assert.True(ok);
    }

    [Fact]
    public void Temp_keeps_naming_the_account_and_folder_it_emptied()
    {
        // %TEMP% is per-user, so a bare "freed 300 MB" is unverifiable — and misleading if
        // the agent ever cleaned an account other than the signed-in one.
        var (ok, msg) = RemediationExecutor.ClearVerdict(
            "temporary files for rpandey", @" in C:\Users\rpandey\AppData\Local\Temp",
            deleted: 120, lockedOut: 0, freedBytes: 50L * 1024 * 1024,
            foundAnything: true, blockedBy: "");

        Assert.True(ok);
        Assert.Contains("rpandey", msg);
        Assert.Contains(@"C:\Users\rpandey\AppData\Local\Temp", msg);
    }

    [Fact]
    public void An_unknown_holder_still_produces_a_usable_message()
    {
        var (ok, msg) = RemediationExecutor.ClearVerdict(
            "browser cache", "", deleted: 0, lockedOut: 5, freedBytes: 0,
            foundAnything: true, blockedBy: "");

        Assert.False(ok);
        Assert.Contains("a running application", msg);
    }
}
