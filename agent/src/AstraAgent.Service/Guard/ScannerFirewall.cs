using AstraAgent.Service.Remediation;
using AstraAgent.Service.Telemetry.Collectors;

namespace AstraAgent.Service.Guard;

/// <summary>One Windows Firewall rule, as far as SAVIO cares about it.</summary>
public sealed record FirewallRule(string Name, string Program, bool Outbound, bool Block, bool Enabled, bool AllProfiles);

/// <summary>The firewall's rule list. The real one is Windows Firewall; tests use their own,
/// so nothing here ever touches the firewall of the PC running the tests.</summary>
public interface IFirewallRules
{
    FirewallRule? Get(string name);
    void Put(FirewallRule rule);
    void Remove(string name);
}

/// <summary>
/// Phase 3 · E4: the scanner has no network. Two Windows Firewall rules block
/// <c>savio-guard-host.exe</c> in both directions on every profile, so even a scanner that
/// misbehaved could not send what it reads anywhere. With the fixed, text-free event schema
/// (E3), this is the trust claim: text is checked on the PC and cannot leave it through SAVIO.
///
/// The rules exist only while the extension is forced in, are checked every cycle, and are put
/// back and reported if someone removes or changes them.
///
/// SAVIO never turns the firewall itself on. That is the organization's setting, and turning
/// it on beside another product can break line-of-business traffic (see FirewallRemediation,
/// an admin-approved action). If Windows Firewall is off, or another firewall is in charge,
/// the rules are still kept, and the report says plainly that the block is not enforced.
/// </summary>
public static class ScannerFirewall
{
    public const string OutboundRule = "SAVIO Guard scanner: no outbound network";
    public const string InboundRule = "SAVIO Guard scanner: no inbound network";

    public static IReadOnlyList<FirewallRule> Desired(string hostExe) =>
    [
        new(OutboundRule, hostExe, Outbound: true, Block: true, Enabled: true, AllProfiles: true),
        new(InboundRule, hostExe, Outbound: false, Block: true, Enabled: true, AllProfiles: true),
    ];

    /// <param name="hostExe">The host's path, or null to remove the rules (no extension forced).</param>
    /// <param name="enforcement">Null when the rules are enforced; otherwise why not.</param>
    public static ApplyReport Apply(IFirewallRules fw, string? hostExe, Func<string?> enforcement)
    {
        List<string> set = [], repaired = [], removed = [];
        if (hostExe is null)
        {
            foreach (var name in new[] { OutboundRule, InboundRule })
                if (fw.Get(name) is not null) { fw.Remove(name); removed.Add(name); }
            return new ApplyReport(Browser.Scanner, set, repaired, removed, [], null);
        }

        foreach (var rule in Desired(hostExe))
        {
            var current = fw.Get(rule.Name);
            if (Same(current, rule)) continue;
            fw.Put(rule);
            (current is null ? set : repaired).Add(rule.Name);
        }
        var notStuck = Desired(hostExe).Where(r => !Same(fw.Get(r.Name), r)).Select(r => r.Name).ToList();
        var error = notStuck.Count > 0
            ? $"Did not stick (something else rewrites them): {string.Join(", ", notStuck)}"
            : enforcement();
        return new ApplyReport(Browser.Scanner, set, repaired, removed, [], error);
    }

    static bool Same(FirewallRule? a, FirewallRule b) =>
        a is not null && a with { Program = a.Program.ToLowerInvariant() } == b with { Program = b.Program.ToLowerInvariant() };

    /// <summary>Why the rules are not being enforced on this PC, or null when they are.</summary>
    public static string? Enforcement()
    {
        try
        {
            if (FirewallRemediation.RegisteredFirewalls() is { } products &&
                FirewallRemediation.OtherFirewalls(products) is { Count: > 0 } others)
                return $"Another firewall is in charge ({string.Join(", ", others)}), so Windows Firewall's block on the "
                       + "scanner is not enforced. Block savio-guard-host.exe's network there.";
            return FirewallRemediation.AllOn(FirewallProfiles.ReadActive())
                ? null
                : "Windows Firewall is off for at least one profile, so the scanner's network block is not enforced there. "
                  + "SAVIO leaves the firewall setting to you.";
        }
        catch (Exception)
        {
            return "Could not read the firewall state, so SAVIO cannot confirm the scanner's network is blocked.";
        }
    }
}

/// <summary>Windows Firewall through its own COM interface (HNetCfg.FwPolicy2), no netsh text.</summary>
public sealed class WindowsFirewallRules : IFirewallRules
{
    const int ActionBlock = 0, DirectionIn = 1, DirectionOut = 2, ProtocolAny = 256, AllProfiles = 0x7FFFFFFF;

    static dynamic Policy() =>
        Activator.CreateInstance(Type.GetTypeFromProgID("HNetCfg.FwPolicy2", throwOnError: true)!)!;

    public FirewallRule? Get(string name)
    {
        dynamic r;
        try { r = Policy().Rules.Item(name); }
        catch (Exception ex) when (ex is FileNotFoundException or System.Runtime.InteropServices.COMException) { return null; }
        return new FirewallRule((string)r.Name, (string?)r.ApplicationName ?? "", (int)r.Direction == DirectionOut,
                                (int)r.Action == ActionBlock, (bool)r.Enabled, (int)r.Profiles == AllProfiles);
    }

    public void Put(FirewallRule rule)
    {
        var rules = Policy().Rules;
        Remove(rule.Name);
        dynamic r = Activator.CreateInstance(Type.GetTypeFromProgID("HNetCfg.FWRule", throwOnError: true)!)!;
        r.Name = rule.Name;
        r.Description = "Set by SAVIO: the AI Guard scanner checks text on this PC and must not reach the network.";
        r.Grouping = "SAVIO";
        r.ApplicationName = rule.Program;
        r.Protocol = ProtocolAny;
        r.Direction = rule.Outbound ? DirectionOut : DirectionIn;
        r.Action = ActionBlock;
        r.Profiles = AllProfiles;
        r.Enabled = rule.Enabled;
        rules.Add(r);
    }

    public void Remove(string name)
    {
        var rules = Policy().Rules;
        // Remove takes out one rule per call; a name could have been duplicated by hand.
        for (int i = 0; i < 10 && Get(name) is not null; i++) rules.Remove(name);
    }
}
