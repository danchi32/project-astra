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
        var (success, output) = await executor.ExecuteAsync("delete_everything", CancellationToken.None);
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
        var (success, _) = await executor.ExecuteAsync(actionId, CancellationToken.None);
        Assert.False(success);
    }

    [Fact]
    public void SupportedActions_AreExactlyTheUserSessionSafeSet()
    {
        Assert.Equal(
            new[] { "clear_temp", "flush_dns", "restart_explorer", "restart_outlook", "restart_teams", "restart_zoom" },
            System.Linq.Enumerable.OrderBy(RemediationExecutor.SupportedActions, x => x).ToArray());
    }
}
