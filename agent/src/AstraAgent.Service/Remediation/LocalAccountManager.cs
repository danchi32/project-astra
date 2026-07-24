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
            // Force the user out of any live session now (the disable alone only blocks the NEXT
            // sign-in). Match the target first; if they can't be matched but exactly one real
            // interactive user is signed in, log that session off too — on an offboarded endpoint
            // that is the person being removed.
            var (loggedOff, sessions) = ForceLogoff(sid);
            string signedOut;
            if (loggedOff > 0)
                signedOut = $"signed {name} out of {loggedOff} live session(s)";
            else if (sessions.Count == 1)
            {
                signedOut = WTSLogoffSession(IntPtr.Zero, sessions[0].SessionId, false)
                    ? $"signed out the active session ({sessions[0].User})"
                    : "couldn't sign out the active session (a reboot will complete it)";
            }
            else if (sessions.Count > 1)
                signedOut = $"{name} was not in an active session ({sessions.Count} other users are "
                          + "signed in — left untouched; reboot to fully clear)";
            else
                signedOut = "no one was signed in";
            return (true, $"Local account '{name}' disabled — {signedOut}. The password is unchanged; "
                        + "re-enable any time to restore access.");
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

    // ── Force-logoff the target account's interactive sessions ────────────────
    // Matches by the account SID (from the session's own user token), NOT by username string —
    // usernames with spaces / different casing / display-vs-SAM forms make string matching
    // unreliable. Returns how many of the target's sessions were logged off, plus every OTHER
    // interactive session so the caller can decide what to do if the target wasn't matched.
    private static (int LoggedOff, List<(int SessionId, string User)> Others) ForceLogoff(string targetSid)
    {
        var loggedOff = 0;
        var others = new List<(int, string)>();
        var infoPtr = IntPtr.Zero;
        try
        {
            if (!WTSEnumerateSessions(IntPtr.Zero, 0, 1, ref infoPtr, out var sessionCount))
                return (0, others);
            var size = Marshal.SizeOf<WTS_SESSION_INFO>();
            var cursor = infoPtr;
            for (var i = 0; i < sessionCount; i++)
            {
                var info = Marshal.PtrToStructure<WTS_SESSION_INFO>(cursor);
                cursor += size;
                // WTS_CONNECTSTATE_CLASS: Active = 0, Disconnected = 4 are the interactive states.
                if (info.State != 0 && info.State != 4) continue;
                var sid = SessionUserSid(info.SessionId);
                if (sid is null) continue;   // no interactive user token (services / session 0)

                if (sid.Equals(targetSid, StringComparison.OrdinalIgnoreCase))
                {
                    if (WTSLogoffSession(IntPtr.Zero, info.SessionId, false)) loggedOff++;
                }
                else
                {
                    others.Add((info.SessionId, QuerySessionString(info.SessionId, 5 /* WTSUserName */)));
                }
            }
        }
        catch { /* best effort */ }
        finally
        {
            if (infoPtr != IntPtr.Zero) WTSFreeMemory(infoPtr);
        }
        return (loggedOff, others);
    }

    private static string QuerySessionString(int sessionId, int infoClass)
    {
        if (!WTSQuerySessionInformation(IntPtr.Zero, sessionId, infoClass, out var buffer, out _))
            return string.Empty;
        try { return Marshal.PtrToStringUni(buffer) ?? string.Empty; }
        finally { if (buffer != IntPtr.Zero) WTSFreeMemory(buffer); }
    }

    /// <summary>The SID string of the user owning <paramref name="sessionId"/>, via that session's
    /// own access token (LocalSystem holds the privilege). Null if it can't be resolved.</summary>
    private static string? SessionUserSid(int sessionId)
    {
        var token = IntPtr.Zero;
        try
        {
            if (!WTSQueryUserToken(sessionId, out token)) return null;
            GetTokenInformation(token, 1 /* TokenUser */, IntPtr.Zero, 0, out var len);
            if (len <= 0) return null;
            var buf = Marshal.AllocHGlobal(len);
            try
            {
                if (!GetTokenInformation(token, 1, buf, len, out _)) return null;
                var user = Marshal.PtrToStructure<TOKEN_USER>(buf);
                if (!ConvertSidToStringSid(user.User.Sid, out var sidPtr)) return null;
                try { return Marshal.PtrToStringUni(sidPtr); }
                finally { LocalFree(sidPtr); }
            }
            finally { Marshal.FreeHGlobal(buf); }
        }
        catch { return null; }
        finally { if (token != IntPtr.Zero) CloseHandle(token); }
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

    // ── Session user-token → SID (robust match, independent of the display name) ──
    [StructLayout(LayoutKind.Sequential)]
    private struct SID_AND_ATTRIBUTES
    {
        public IntPtr Sid;
        public int Attributes;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct TOKEN_USER
    {
        public SID_AND_ATTRIBUTES User;
    }

    [DllImport("wtsapi32.dll", SetLastError = true)]
    private static extern bool WTSQueryUserToken(int sessionId, out IntPtr phToken);

    [DllImport("advapi32.dll", SetLastError = true)]
    private static extern bool GetTokenInformation(
        IntPtr tokenHandle, int tokenInformationClass, IntPtr tokenInformation,
        int tokenInformationLength, out int returnLength);

    [DllImport("advapi32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    private static extern bool ConvertSidToStringSid(IntPtr sid, out IntPtr stringSid);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool CloseHandle(IntPtr handle);

    [DllImport("kernel32.dll")]
    private static extern IntPtr LocalFree(IntPtr handle);
}
