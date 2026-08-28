using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Management;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text.RegularExpressions;

namespace AstraAgent.Service.Remediation;

/// <summary>Resets a LOCAL Windows account's password to a freshly generated one and requires
/// the person to change it at their next sign-in.
///
/// Two decisions here are the whole design:
///
/// 1. THE AGENT GENERATES THE PASSWORD. The portal never sends one, so no password an
///    administrator chose travels over the network, lands in `remediation_tasks.params`, or
///    appears in an audit entry. A parameter the backend stores is a parameter that outlives
///    the moment it was needed.
///
/// 2. IT IS SET WITH NetUserSetInfo, NOT `net user`. `net user X <password>` puts the secret
///    in a process command line, and on Windows any local process can read another's command
///    line. It would be exposed for the lifetime of that net.exe — brief, and briefly is
///    plenty. The API call takes it as a string in this process's own memory and nowhere else.
///
/// The new password is returned to the caller (and so to the portal, once, in the task
/// result) because that is the only way it reaches the technician who has to read it to the
/// locked-out user. It is single-use by construction: the account must change it at the next
/// sign-in, so a copy left behind in a task result is a password that no longer works.
///
/// Local accounts only. A domain or Entra account is refused rather than attempted: this API
/// operates on the local SAM, so on a domain account it would report success having changed
/// nothing the user signs in with — which is worse than a refusal, because the technician
/// tells them a password that does not work.</summary>
public static class LocalPasswordReset
{
    private static readonly Regex NameOk = new(@"^[A-Za-z0-9][A-Za-z0-9 ._-]{0,62}$", RegexOptions.Compiled);
    // Built-in accounts by RID: Administrator (500), Guest (501), DefaultAccount (503),
    // WDAGUtilityAccount (504). Same set LocalAccountManager protects, for the same reason.
    private static readonly HashSet<string> ProtectedRids = new() { "500", "501", "503", "504" };

    /// <summary>Normalizes and validates the account name, without touching the machine.
    ///
    /// Split out so it can be tested: whether "ACME\olivia" means the local account "olivia",
    /// and whether a name carrying a path separator or a quote is refused, are decisions worth
    /// holding, and neither needs a real SAM to check.</summary>
    internal static (string? Name, string? Refusal) NormalizeName(string? username)
    {
        var name = (username ?? string.Empty).Trim();
        // The portal prefills from a session's "DOMAIN\user"; keep the account part.
        if (name.Contains('\\')) name = name[(name.LastIndexOf('\\') + 1)..].Trim();
        if (!NameOk.IsMatch(name))
            return (null, $"'{username}' is not a valid local account name.");
        return (name, null);
    }

    public static (bool, string) Reset(string? username)
    {
        var (normalized, refusal) = NormalizeName(username);
        if (normalized is null) return (false, refusal!);
        var name = normalized;

        var found = FindLocalUser(name);
        if (found is null)
            return (false,
                $"'{name}' is not a local account on this machine. Domain and Entra accounts are "
                + "reset in Active Directory or Entra ID — the agent cannot change them, and "
                + "pretending otherwise would hand you a password that does not work.");

        var (sid, _) = found.Value;
        var rid = sid.Contains('-') ? sid[(sid.LastIndexOf('-') + 1)..] : string.Empty;
        if (ProtectedRids.Contains(rid))
            return (false, $"'{name}' is a built-in Windows account and cannot be reset by ASTRA.");

        var password = GeneratePassword();
        var info = new USER_INFO_1003 { Password = password };
        var status = NetUserSetInfo(null, name, 1003, ref info, out var badParam);
        if (status != 0)
            return (false, DescribeFailure(status, badParam, name));

        // Force a change at next sign-in, so the password that just travelled through the
        // portal stops working the moment it has done its job. Best effort and reported
        // honestly: an account marked "password never expires" refuses this flag, and a
        // technician who is told the reset worked deserves to know the temporary password
        // will keep working until someone changes it.
        var forced = ForceChangeAtNextLogon(name);

        return (true,
            $"Password reset for local account '{name}'.\n\n"
            + $"Temporary password: {password}\n\n"
            + (forced
                ? "They must choose a new one at their next sign-in, so read it to them and "
                  + "do not keep it."
                : "NOTE: Windows would not set 'must change at next sign-in' on this account "
                  + "(it is probably set to 'password never expires'), so this temporary "
                  + "password will keep working until someone changes it. Change it once they "
                  + "are back in."));
    }

    /// <summary>16 characters with at least one of each class, drawn from a cryptographic RNG.
    ///
    /// Ambiguous glyphs (0/O, 1/l/I) are left out on purpose. This password's entire job is to
    /// be read aloud down a phone line to someone locked out of their machine, and a password
    /// that cannot survive that is a password that generates a second support call.</summary>
    internal static string GeneratePassword()
    {
        const string lower = "abcdefghijkmnpqrstuvwxyz";
        const string upper = "ABCDEFGHJKLMNPQRSTUVWXYZ";
        const string digits = "23456789";
        const string symbols = "!@#$%^&*-_=+";
        const string all = lower + upper + digits + symbols;

        var chars = new char[16];
        chars[0] = Pick(lower);
        chars[1] = Pick(upper);
        chars[2] = Pick(digits);
        chars[3] = Pick(symbols);
        for (var i = 4; i < chars.Length; i++) chars[i] = Pick(all);

        // Shuffle, so the guaranteed classes are not always in the first four positions.
        for (var i = chars.Length - 1; i > 0; i--)
        {
            var j = RandomNumberGenerator.GetInt32(i + 1);
            (chars[i], chars[j]) = (chars[j], chars[i]);
        }
        return new string(chars);
    }

    private static char Pick(string set) => set[RandomNumberGenerator.GetInt32(set.Length)];

    private static bool ForceChangeAtNextLogon(string name)
    {
        try
        {
            var psi = new ProcessStartInfo
            {
                FileName = "net.exe",
                UseShellExecute = false,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                CreateNoWindow = true,
            };
            psi.ArgumentList.Add("user");
            psi.ArgumentList.Add(name);            // one argv element — never a shell string
            psi.ArgumentList.Add("/logonpasswordchg:yes");
            using var p = Process.Start(psi);
            if (p is null) return false;
            p.StandardOutput.ReadToEnd();
            p.StandardError.ReadToEnd();
            p.WaitForExit(30000);
            return p.ExitCode == 0;
        }
        catch { return false; }
    }

    private static (string Sid, bool Disabled)? FindLocalUser(string name)
    {
        try
        {
            using var search = new ManagementObjectSearcher(
                "SELECT SID, Disabled FROM Win32_UserAccount WHERE LocalAccount=True AND Name='"
                + name.Replace("'", "''") + "'");
            foreach (ManagementObject u in search.Get())
            {
                var sid = (string)(u["SID"] ?? string.Empty);
                if (!string.IsNullOrEmpty(sid))
                    return (sid, (bool)(u["Disabled"] ?? false));
            }
        }
        catch { /* treated as "not found" */ }
        return null;
    }

    /// <summary>Turns NetUserSetInfo's status code into something a technician can act on.
    /// The two that actually happen are a password policy the generated one somehow failed,
    /// and an account the service may not modify.</summary>
    private static string DescribeFailure(uint status, uint badParam, string name) => status switch
    {
        2245 => $"Windows rejected the generated password for '{name}' as not meeting this "
              + "machine's password policy (NERR_PasswordTooShort). The policy may require "
              + "more than 16 characters.",
        5 => $"Access denied changing '{name}'. The account may be managed by policy.",
        2221 => $"'{name}' does not exist on this machine.",
        _ => $"Windows refused the password reset for '{name}' (status {status}, parameter {badParam}).",
    };

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct USER_INFO_1003
    {
        [MarshalAs(UnmanagedType.LPWStr)] public string Password;
    }

    [DllImport("netapi32.dll", CharSet = CharSet.Unicode, ExactSpelling = true)]
    private static extern uint NetUserSetInfo(
        string? serverName, string userName, uint level,
        ref USER_INFO_1003 buf, out uint parmError);
}
