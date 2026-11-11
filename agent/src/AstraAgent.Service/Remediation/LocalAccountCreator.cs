using System;
using System.Management;
using System.Runtime.InteropServices;
using System.Security.Principal;
using System.Text.RegularExpressions;

namespace AstraAgent.Service.Remediation;

/// <summary>Creates a new LOCAL Windows account (A1).
///
/// Same rules as <see cref="LocalPasswordReset"/>, for the same reasons:
///
/// 1. THE AGENT GENERATES THE PASSWORD. The portal never sends one, so no chosen password
///    crosses the network or lands in a stored task parameter.
/// 2. NetUserAdd, NOT `net user /add`. A password on a command line is readable by any local
///    process for as long as net.exe runs.
/// 3. The person must change it at first sign-in, so the copy in the task result stops working
///    the moment it has done its job.
///
/// Group membership is set by well-known SID (Users S-1-5-32-545, Administrators S-1-5-32-544)
/// and translated to this machine's group name — on a German Windows "Users" is "Benutzer",
/// and a hardcoded English name would fail exactly where nobody is looking.</summary>
public static class LocalAccountCreator
{
    // Windows caps SAM account names at 20 characters; same character set as the backend.
    private static readonly Regex NameOk = new(@"^[A-Za-z0-9](?:[A-Za-z0-9 ._-]{0,18}[A-Za-z0-9.])?$", RegexOptions.Compiled);

    internal const string UsersSid = "S-1-5-32-545";
    internal const string AdministratorsSid = "S-1-5-32-544";

    internal static string? Refusal(string? username, string? fullName)
    {
        var name = (username ?? string.Empty).Trim();
        if (name.Contains('\\') || !NameOk.IsMatch(name))
            return $"'{username}' can't be a local account name: up to 20 letters, digits, spaces, '.', '_' or '-'.";
        if ((fullName ?? string.Empty).Length > 100)
            return "Full name is longer than 100 characters.";
        return null;
    }

    public static (bool, string) Create(string? username, string? fullName, string? makeAdmin)
    {
        var refusal = Refusal(username, fullName);
        if (refusal is not null) return (false, refusal);
        var name = username!.Trim();
        var admin = string.Equals(makeAdmin, "true", StringComparison.OrdinalIgnoreCase);

        if (IsDomainController())
            return (false, "This machine is a domain controller — it has no local accounts. Create the "
                           + "user in Active Directory instead.");

        var password = LocalPasswordReset.GeneratePassword();
        var info = new USER_INFO_1
        {
            Name = name,
            Password = password,
            Priv = 1,                       // USER_PRIV_USER
            Comment = "Created by SAVIO",
            Flags = 0x0001 | 0x0200,        // UF_SCRIPT | UF_NORMAL_ACCOUNT
        };
        var status = NetUserAdd(null, 1, ref info, out var badParam);
        if (status != 0)
            return (false, DescribeFailure(status, badParam, name));

        var notes = new System.Collections.Generic.List<string>();

        var full = (fullName ?? string.Empty).Trim();
        if (full.Length > 0)
        {
            var fn = new USER_INFO_1011 { FullName = full };
            if (NetUserSetInfo(null, name, 1011, ref fn, out _) != 0)
                notes.Add("The full name could not be set.");
        }

        // Users explicitly: an account in no group can't sign in interactively on some SKUs.
        if (!AddToGroup(UsersSid, name))
            notes.Add("Could not add the account to the Users group — it may not be able to sign in.");
        if (admin && !AddToGroup(AdministratorsSid, name))
            notes.Add("Could NOT add the account to Administrators — it was created as a standard user.");

        var forced = LocalPasswordReset.ForceChangeAtNextLogon(name);

        return (true,
            $"Created local account '{name}'{(admin ? " (Administrator)" : "")}.\n\n"
            + $"One-time password: {password}\n\n"
            + (forced
                ? "They must choose a new password at first sign-in, so share it once and do not keep it."
                : "NOTE: Windows would not set 'must change at next sign-in', so this password "
                  + "keeps working until someone changes it.")
            + (notes.Count > 0 ? "\n\n" + string.Join("\n", notes) : ""));
    }

    internal static bool AddToGroup(string groupSid, string user)
    {
        try
        {
            var group = new SecurityIdentifier(groupSid).Translate(typeof(NTAccount)).Value;
            group = group[(group.LastIndexOf('\\') + 1)..];     // "BUILTIN\Users" -> "Users"
            var member = new LOCALGROUP_MEMBERS_INFO_3 { DomainAndName = $"{Environment.MachineName}\\{user}" };
            var status = NetLocalGroupAddMembers(null, group, 3, ref member, 1);
            return status == 0 || status == 1378;               // 1378: already a member
        }
        catch { return false; }
    }

    internal static bool RemoveFromGroup(string groupSid, string user)
    {
        try
        {
            var group = new SecurityIdentifier(groupSid).Translate(typeof(NTAccount)).Value;
            group = group[(group.LastIndexOf('\\') + 1)..];
            var member = new LOCALGROUP_MEMBERS_INFO_3 { DomainAndName = $"{Environment.MachineName}\\{user}" };
            var status = NetLocalGroupDelMembers(null, group, 3, ref member, 1);
            return status == 0 || status == 1377;               // 1377: not a member
        }
        catch { return false; }
    }

    private static bool IsDomainController()
    {
        try
        {
            using var s = new ManagementObjectSearcher("SELECT DomainRole FROM Win32_ComputerSystem");
            foreach (var o in s.Get())
                return Convert.ToInt32(o["DomainRole"]) >= 4;   // 4 backup DC, 5 primary DC
        }
        catch { /* unknown: let NetUserAdd decide */ }
        return false;
    }

    private static string DescribeFailure(uint status, uint badParam, string name) => status switch
    {
        2224 => $"An account named '{name}' already exists on this machine.",
        1379 => $"'{name}' is already the name of a group on this machine.",
        2245 => "Windows rejected the generated password as not meeting this machine's password "
              + "policy. The policy may require more than 16 characters.",
        5 => "Access denied creating the account. Local accounts may be blocked by policy here.",
        _ => $"Windows refused to create '{name}' (status {status}, parameter {badParam}).",
    };

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct USER_INFO_1
    {
        [MarshalAs(UnmanagedType.LPWStr)] public string Name;
        [MarshalAs(UnmanagedType.LPWStr)] public string Password;
        public uint PasswordAge;
        public uint Priv;
        [MarshalAs(UnmanagedType.LPWStr)] public string? HomeDir;
        [MarshalAs(UnmanagedType.LPWStr)] public string? Comment;
        public uint Flags;
        [MarshalAs(UnmanagedType.LPWStr)] public string? ScriptPath;
    }

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct USER_INFO_1011
    {
        [MarshalAs(UnmanagedType.LPWStr)] public string FullName;
    }

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct LOCALGROUP_MEMBERS_INFO_3
    {
        [MarshalAs(UnmanagedType.LPWStr)] public string DomainAndName;
    }

    [DllImport("netapi32.dll", CharSet = CharSet.Unicode, ExactSpelling = true)]
    private static extern uint NetUserAdd(string? serverName, uint level, ref USER_INFO_1 buf, out uint parmError);

    [DllImport("netapi32.dll", CharSet = CharSet.Unicode, ExactSpelling = true)]
    private static extern uint NetUserSetInfo(string? serverName, string userName, uint level,
        ref USER_INFO_1011 buf, out uint parmError);

    [DllImport("netapi32.dll", CharSet = CharSet.Unicode, ExactSpelling = true)]
    private static extern uint NetLocalGroupDelMembers(string? serverName, string groupName, uint level,
        ref LOCALGROUP_MEMBERS_INFO_3 buf, uint totalEntries);

    [DllImport("netapi32.dll", CharSet = CharSet.Unicode, ExactSpelling = true)]
    private static extern uint NetLocalGroupAddMembers(string? serverName, string groupName, uint level,
        ref LOCALGROUP_MEMBERS_INFO_3 buf, uint totalEntries);
}
