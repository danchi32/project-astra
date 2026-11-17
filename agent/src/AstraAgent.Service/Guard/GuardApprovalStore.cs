using System.Security.AccessControl;
using System.Security.Principal;
using AstraAgent.Guard;
using AstraAgent.Service.Api;
using Microsoft.Win32;

namespace AstraAgent.Service.Guard;

/// <summary>
/// Phase 3 · D7: puts the approvals in force where the native host can read them: one key per
/// Windows account, <c>HKLM\SOFTWARE\SAVIO\GuardApprovals\&lt;SID&gt;</c>.
///
/// Each key is readable by that account only (plus SYSTEM and Administrators, who can change
/// it). Inheritance is cut, so the "Users: read" that HKLM\SOFTWARE hands down does not let
/// one person see another's approvals. A standard user cannot create or change keys under
/// HKLM\SOFTWARE, so nobody can plant an approval for themselves. An account Windows cannot
/// name (deleted, or a typo) is skipped, and keys for accounts with nothing in force are removed.
/// </summary>
public sealed class GuardApprovalStore(
    RegistryKey root, Func<string, string?> sidOf, Func<SecurityIdentifier, RegistrySecurity> security,
    Func<RegistrySecurity>? parentSecurity = null)
{
    public static void WriteMachine(IReadOnlyList<AgentGuardApproval> approvals) =>
        new GuardApprovalStore(Registry.LocalMachine, SidOf, ReadableBy).Write(approvals);

    public void Write(IReadOnlyList<AgentGuardApproval> approvals)
    {
        var bySid = new Dictionary<string, string[]>(StringComparer.OrdinalIgnoreCase);
        foreach (var g in approvals.GroupBy(a => a.WindowsUser, StringComparer.OrdinalIgnoreCase))
            if (sidOf(g.Key) is { } sid)
                bySid[sid] = g.Select(a => GuardApprovals.Format(a.Site, a.Channel, a.ValidUntil)).Order().ToArray();

        if (bySid.Count == 0)
        {
            root.DeleteSubKeyTree(GuardApprovals.KeyPath, throwOnMissingSubKey: false);
            return;
        }
        using var parent = root.CreateSubKey(GuardApprovals.KeyPath, writable: true);
        // Security review L4: the parent lists one subkey per account with an approval in force.
        // Nobody but SYSTEM and Administrators may list it; each person opens their own subkey
        // by its full path (the registry checks only the key being opened).
        parent.SetAccessControl((parentSecurity ?? AdminsOnly)());
        foreach (var stale in parent.GetSubKeyNames().Where(s => !bySid.ContainsKey(s)))
            parent.DeleteSubKeyTree(stale, throwOnMissingSubKey: false);
        foreach (var (sid, entries) in bySid)
        {
            using var key = parent.CreateSubKey(sid, writable: true);
            key.SetAccessControl(security(new SecurityIdentifier(sid)));
            if (!(key.GetValue(GuardApprovals.ValueName) as string[] ?? []).SequenceEqual(entries))
                key.SetValue(GuardApprovals.ValueName, entries, RegistryValueKind.MultiString);
        }
    }

    static string? SidOf(string account)
    {
        try { return ((SecurityIdentifier)new NTAccount(account).Translate(typeof(SecurityIdentifier))).Value; }
        catch (Exception ex) when (ex is IdentityNotMappedException or SystemException) { return null; }
    }

    internal static RegistrySecurity AdminsOnly()
    {
        var s = new RegistrySecurity();
        s.SetAccessRuleProtection(isProtected: true, preserveInheritance: false);
        foreach (var admin in new[] { WellKnownSidType.LocalSystemSid, WellKnownSidType.BuiltinAdministratorsSid })
            s.AddAccessRule(new RegistryAccessRule(new SecurityIdentifier(admin, null), RegistryRights.FullControl,
                InheritanceFlags.None, PropagationFlags.None, AccessControlType.Allow));
        return s;
    }

    /// <summary>SYSTEM and Administrators in full, the account itself read-only, nothing inherited.</summary>
    internal static RegistrySecurity ReadableBy(SecurityIdentifier account)
    {
        var s = new RegistrySecurity();
        s.SetAccessRuleProtection(isProtected: true, preserveInheritance: false);
        foreach (var admin in new[] { WellKnownSidType.LocalSystemSid, WellKnownSidType.BuiltinAdministratorsSid })
            s.AddAccessRule(new RegistryAccessRule(new SecurityIdentifier(admin, null), RegistryRights.FullControl,
                InheritanceFlags.ContainerInherit, PropagationFlags.None, AccessControlType.Allow));
        s.AddAccessRule(new RegistryAccessRule(account, RegistryRights.ReadKey,
            InheritanceFlags.ContainerInherit, PropagationFlags.None, AccessControlType.Allow));
        return s;
    }
}
