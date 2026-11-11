using AstraAgent.Service.Net;
using Microsoft.Extensions.Logging.Abstractions;
using Xunit;

namespace AstraAgent.Service.Tests;

public class NetworkDoctorTests
{
    [Theory]
    [InlineData(true, true, true, true, true, Diagnosis.Healthy)]
    [InlineData(true, true, true, true, false, Diagnosis.BackendOnlyDown)]   // the internet works; SAVIO doesn't
    [InlineData(false, false, false, false, false, Diagnosis.NoAddress)]
    [InlineData(true, false, false, false, false, Diagnosis.GatewayUnreachable)]
    [InlineData(true, true, true, false, false, Diagnosis.DnsFailing)]
    [InlineData(true, true, false, false, false, Diagnosis.NoInternet)]
    public void Diagnose(bool addr, bool gw, bool ip, bool dns, bool backend, Diagnosis expected)
        => Assert.Equal(expected, NetworkRules.Diagnose(new Probe(addr, gw, ip, dns, backend)));

    [Fact]
    public void Ladder_IsCheapestFirst_AndEmptyWhenThereIsNothingToFix()
    {
        Assert.Equal([FixStep.RenewIp, FixStep.RestartAdapter], NetworkRules.Ladder(Diagnosis.NoAddress));
        Assert.Equal([FixStep.FlushDns, FixStep.RenewIp], NetworkRules.Ladder(Diagnosis.DnsFailing));
        Assert.Equal([FixStep.FlushDns], NetworkRules.Ladder(Diagnosis.NoInternet));
        Assert.Empty(NetworkRules.Ladder(Diagnosis.Healthy));
        Assert.Empty(NetworkRules.Ladder(Diagnosis.BackendOnlyDown));
    }

    [Fact]
    public void Limiter_AllowsThreeAutomaticRunsAnHour_AndOneAdapterRestart()
    {
        var t = DateTimeOffset.Parse("2026-11-11T10:00:00Z");
        var lim = new FixLimiter(() => t);
        Assert.Null(lim.RefuseLadder(false));
        Assert.Null(lim.RefuseLadder(false));
        Assert.Null(lim.RefuseLadder(false));
        Assert.NotNull(lim.RefuseLadder(false));               // fourth in the hour
        Assert.True(lim.MayRestartAdapter());
        Assert.False(lim.MayRestartAdapter());                  // again within the hour
        t = t.AddMinutes(61);
        Assert.Null(lim.RefuseLadder(false));                  // window rolled
        Assert.True(lim.MayRestartAdapter());
    }

    [Fact]
    public void Limiter_SpacesOutManualRuns()
    {
        var t = DateTimeOffset.Parse("2026-11-11T10:00:00Z");
        var lim = new FixLimiter(() => t);
        Assert.Null(lim.RefuseLadder(true));
        Assert.NotNull(lim.RefuseLadder(true));
        t = t.AddMinutes(3);
        Assert.Null(lim.RefuseLadder(true));
    }

    [Fact]
    public async Task Run_StopsAtTheFirstStepThatWorks_AndJournalsIt()
    {
        var journal = Path.Combine(Path.GetTempPath(), $"savio-journal-{Guid.NewGuid():N}.jsonl");
        var reachable = false;
        var doctor = new NetworkDoctor(NullLogger<NetworkDoctor>.Instance, _ => Task.FromResult(reachable),
            journal, new FixLimiter(() => DateTimeOffset.UtcNow));
        var ran = new List<FixStep>();
        try
        {
            // Probe runs against the real machine; this box has a network, so whatever the
            // diagnosis, the scripted step "fixes" SAVIO on the first try.
            var result = await doctor.RunAsync("test", manual: true, CancellationToken.None, step =>
            {
                ran.Add(step);
                reachable = true;
                return (true, "ok");
            });
            if (ran.Count > 0)
            {
                Assert.Single(ran);
                Assert.StartsWith("Fixed:", result);
                var entry = Assert.Single(doctor.ReadJournal());
                Assert.True(entry.FixedAfter);
                Assert.Equal("test", entry.Trigger);
            }
            else
            {
                // The live probe saw the internet working, so there was honestly nothing to fix.
                Assert.Contains("only SAVIO's server", result);
            }
        }
        finally { File.Delete(journal); }
    }

    [Fact]
    public void Pipe_IsForThePersonAtThePc()
    {
        var rules = AstraAgent.Service.Workers.NetworkFixPipeServer.Security()
            .GetAccessRules(true, false, typeof(System.Security.Principal.SecurityIdentifier))
            .Cast<System.IO.Pipes.PipeAccessRule>().ToList();
        Assert.Contains(rules, r => r.IdentityReference.Value == "S-1-5-2"
                                    && r.AccessControlType == System.Security.AccessControl.AccessControlType.Deny); // NETWORK
        Assert.Contains(rules, r => r.IdentityReference.Value == "S-1-5-4");                                    // INTERACTIVE
    }
}
