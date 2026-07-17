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

    [Theory]
    [InlineData("office_repair")]     // approval-required, no desktop handler
    [InlineData("registry_fix")]      // admin-only
    [InlineData("restart_service")]   // elevated
    [InlineData("network_reset")]     // elevated
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
}
