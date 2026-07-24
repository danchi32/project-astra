using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Management;
using System.Runtime.InteropServices;
using System.Text.RegularExpressions;

namespace AstraAgent.Service.Remediation;

/// <summary>Enables/disables a LOCAL Windows account for secure offboarding, running as
/// LocalSystem. It never changes a password or deletes anything — it only toggles the account's
/// "active" flag and, on disable, signs the user out of any live session. Fully reversible.
///
/// Guardrails (defense in depth, independent of the backend):
///   * only ever acts on a real LOCAL account (domain/Entra accounts are refused);
///   * never touches built-in accounts (Administrator/Guest/DefaultAccount/WDAGUtility by RID);
///   * refuses to disable the last active local administrator (would lock the machine out).</summary>
public static class LocalAccountManager
{
    private static readonly Regex NameOk = new(@"^[A-Za-z0-9][A-Za-z0-9 ._-]{0,62}$", RegexOptions.Compiled);
    private static readonly HashSet<string> ProtectedRids = new() { "500", "501", "503", "504" };

    public static (bool, string) SetEnabled(string? username, bool enable)
    {
        var name = (username ?? string.Empty).Trim();
        if (!NameOk.IsMatch(name))
            return (false, $"'{name}' is not a valid local account name.");

        var target = FindLocalUser(name);
        if (target is null)
            return (false, $"'{name}' is not a local account on this machine. Domain/Entra accounts "
                         + "are managed in Active Directory / Intune, not by the agent.");

        var (sid, disabled) = target.Value;
        var rid = sid.Contains('-') ? sid[(sid.LastIndexOf('-') + 1)..] : string.Empty;
        if (ProtectedRids.Contains(rid))
            return (false, $"'{name}' is a built-in Windows account and cannot be changed.");

        if (enable)
        {
            if (!disabled) return (true, $"Account '{name}' is already active — nothing to do.");
        }
        else
        {
            if (disabled) return (true, $"Account '{name}' is already disabled — nothing to do.");
            var refusal = LastAdminGuard(sid);
            if (refusal is not null) return (false, refusal);
        }

        var (ok, output) = RunNet(name, enable ? "/active:yes" : "/active:no");
        if (!ok) return (false, output);

        if (!enable)
        {
            var kicked = TryLogoff(name);   // best-effort: the disable already took effect
            return (true, $"Local account '{name}' disabled and signed out ({kicked} active session(s)). "
                        + "The password is unchanged — re-enable any time to restore access.");
        }
        return (true, $"Local account '{name}' re-enabled — the user can sign in again with their "
                    + "existing password.");
    }

    private static (string Sid, bool Disabled)? FindLocalUser(string name)
    {
        try
        {
            using var s = new ManagementObjectSearcher(
                "SELECT SID, Disabled FROM Win32_UserAccount WHERE LocalAccount=True AND Name='"
                + name.Replace("'", "''") + "'");
            foreach (ManagementObject u in s.Get())
            {
                var sid = (string)(u["SID"] ?? string.Empty);
                if (!string.IsNullOrEmpty(sid))
                    return (sid, (bool)(u["Disabled"] ?? false));
            }
        }
        catch { /* treated as "not found" */ }
        return null;
    }

    /// <summary>A refusal message if disabling <paramref name="targetSid"/> would (or might) leave
    /// no enabled local administrator; null when it's provably safe. Fail-SAFE: if local-admin
    /// membership can't be evaluated, we refuse rather than risk locking the machine out — the admin
    /// can retry. (Only direct user members of Administrators are counted; an account that is admin
    /// solely via a nested group is a rare edge that this does not attempt to resolve.)</summary>
    private static string? LastAdminGuard(string targetSid)
    {
        const string cannotVerify =
            "Refusing: couldn't verify local-administrator membership on this machine, so the agent "
            + "won't risk disabling the last admin. Please try again.";
        try
        {
            string? adminGroup = null;
            using (var gs = new ManagementObjectSearcher(
                "SELECT Name FROM Win32_Group WHERE LocalAccount=True AND SID='S-1-5-32-544'"))
            {
                foreach (ManagementObject g in gs.Get()) { adminGroup = (string)g["Name"]; break; }
            }
            if (adminGroup is null) return cannotVerify;   // fail-safe: can't resolve the group

            using var grp = new ManagementObject(
                $"Win32_Group.Domain='{Environment.MachineName}',Name='{adminGroup}'");
            var targetIsAdmin = false;
            var otherEnabledAdmins = 0;
            foreach (ManagementObject m in grp.GetRelated("Win32_UserAccount"))
            {
                var mSid = (string)(m["SID"] ?? string.Empty);
                if (mSid == targetSid) { targetIsAdmin = true; continue; }
                if ((bool)(m["LocalAccount"] ?? false) && !(bool)(m["Disabled"] ?? false))
                    otherEnabledAdmins++;
            }
            if (targetIsAdmin && otherEnabledAdmins == 0)
                return "Refusing: that account is the last active local administrator — disabling it "
                     + "would lock this machine out of management. Enable another admin first.";
            return null;
        }
        catch
        {
            return cannotVerify;   // fail-safe: membership couldn't be evaluated
        }
    }

    private static (bool, string) RunNet(string username, string flag)
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
            psi.ArgumentList.Add(username);   // a single argv element — never a shell string
            psi.ArgumentList.Add(flag);
            using var p = Process.Start(psi)!;
            var so = p.StandardOutput.ReadToEnd();
            var se = p.StandardError.ReadToEnd();
            p.WaitForExit(30000);
            if (p.ExitCode == 0) return (true, "ok");
            var msg = string.IsNullOrWhiteSpace(se) ? so : se;
            return (false, $"Windows rejected the change: {msg.Trim()}");
        }
        catch (Exception ex)
        {
            return (false, "Failed to run the account change: " + ex.Message);
        }
    }

    // ── Best-effort force-logoff of the target user's interactive sessions ─────
    private static int TryLogoff(string username)
    {
        var count = 0;
        var infoPtr = IntPtr.Zero;
        try
        {
            if (!WTSEnumerateSessions(IntPtr.Zero, 0, 1, ref infoPtr, out var sessionCount))
                return 0;
            var size = Marshal.SizeOf<WTS_SESSION_INFO>();
            var cursor = infoPtr;
            for (var i = 0; i < sessionCount; i++)
            {
                var info = Marshal.PtrToStructure<WTS_SESSION_INFO>(cursor);
                cursor += size;
                if (!WTSQuerySessionInformation(IntPtr.Zero, info.SessionId, 5 /* WTSUserName */,
                        out var buffer, out _))
                    continue;
                var user = Marshal.PtrToStringUni(buffer) ?? string.Empty;
                WTSFreeMemory(buffer);
                if (user.Equals(username, StringComparison.OrdinalIgnoreCase)
                    && WTSLogoffSession(IntPtr.Zero, info.SessionId, false))
                    count++;
            }
        }
        catch { /* best effort */ }
        finally
        {
            if (infoPtr != IntPtr.Zero) WTSFreeMemory(infoPtr);
        }
        return count;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct WTS_SESSION_INFO
    {
        public int SessionId;
        [MarshalAs(UnmanagedType.LPWStr)] public string pWinStationName;
        public int State;
    }

    [DllImport("wtsapi32.dll", SetLastError = true)]
    private static extern bool WTSEnumerateSessions(
        IntPtr hServer, int reserved, int version, ref IntPtr ppSessionInfo, out int pCount);

    [DllImport("wtsapi32.dll")]
    private static extern void WTSFreeMemory(IntPtr memory);

    [DllImport("wtsapi32.dll", SetLastError = true)]
    private static extern bool WTSQuerySessionInformation(
        IntPtr hServer, int sessionId, int wtsInfoClass, out IntPtr ppBuffer, out int pBytesReturned);

    [DllImport("wtsapi32.dll", SetLastError = true)]
    private static extern bool WTSLogoffSession(IntPtr hServer, int sessionId, bool bWait);
}
