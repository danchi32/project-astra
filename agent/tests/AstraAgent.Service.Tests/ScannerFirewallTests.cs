using AstraAgent.Service.Guard;
using Xunit;

namespace AstraAgent.Service.Tests;

/// <summary>
/// Phase 3 · E4: the scanner's network block. Runs against an in-memory rule list: these tests
/// never touch the firewall of the PC running them.
/// </summary>
public class ScannerFirewallTests
{
    sealed class Rules : IFirewallRules
    {
        public readonly Dictionary<string, FirewallRule> All = new(StringComparer.OrdinalIgnoreCase);
        public bool IgnoreWrites;
        public FirewallRule? Get(string name) => All.GetValueOrDefault(name);
        public void Put(FirewallRule rule) { if (!IgnoreWrites) All[rule.Name] = rule; }
        public void Remove(string name) => All.Remove(name);
    }

    const string Exe = @"C:\Program Files\SAVIO\Agent\savio-guard-host.exe";
    static string? Enforced() => null;

    [Fact]
    public void Blocks_the_scanner_both_ways_on_every_profile()
    {
        var fw = new Rules();
        var r = ScannerFirewall.Apply(fw, Exe, Enforced);
        Assert.Equal(Browser.Scanner, r.Browser);
        Assert.Null(r.Error);
        Assert.Equal(2, r.Set.Count);
        Assert.All(fw.All.Values, rule =>
        {
            Assert.Equal(Exe, rule.Program);
            Assert.True(rule.Block && rule.Enabled && rule.AllProfiles);
        });
        Assert.Contains(fw.All.Values, x => x.Outbound);
        Assert.Contains(fw.All.Values, x => !x.Outbound);

        Assert.False(ScannerFirewall.Apply(fw, Exe, Enforced).Changed);                 // idempotent
        Assert.False(ScannerFirewall.Apply(fw, Exe.ToUpperInvariant(), Enforced).Changed);   // paths are case-blind
    }

    [Fact]
    public void A_removed_or_weakened_rule_is_put_back_and_reported()
    {
        var fw = new Rules();
        ScannerFirewall.Apply(fw, Exe, Enforced);
        fw.Remove(ScannerFirewall.InboundRule);                                          // deleted by hand
        fw.All[ScannerFirewall.OutboundRule] = fw.All[ScannerFirewall.OutboundRule] with { Enabled = false };   // or switched off
        var r = ScannerFirewall.Apply(fw, Exe, Enforced);
        Assert.Equal([ScannerFirewall.OutboundRule], r.Repaired);
        Assert.Equal([ScannerFirewall.InboundRule], r.Set);
        Assert.True(fw.All[ScannerFirewall.OutboundRule].Enabled);
    }

    [Fact]
    public void Says_so_when_the_block_is_not_in_force()
    {
        var off = ScannerFirewall.Apply(new Rules(), Exe, () => "Windows Firewall is off for at least one profile");
        Assert.Contains("off", off.Error);                                               // never silently "applied"

        var stuck = ScannerFirewall.Apply(new Rules { IgnoreWrites = true }, Exe, Enforced);
        Assert.StartsWith("Did not stick", stuck.Error);
    }

    [Fact]
    public void Rules_go_when_the_extension_does()
    {
        var fw = new Rules();
        ScannerFirewall.Apply(fw, Exe, Enforced);
        fw.All["Someone else's rule"] = new("Someone else's rule", @"C:\x.exe", true, true, true, true);
        var r = ScannerFirewall.Apply(fw, null, Enforced);
        Assert.Equal(2, r.Removed.Count);
        Assert.Equal(["Someone else's rule"], fw.All.Keys);                              // only ours removed
        Assert.False(ScannerFirewall.Apply(fw, null, Enforced).Changed);
    }
}
