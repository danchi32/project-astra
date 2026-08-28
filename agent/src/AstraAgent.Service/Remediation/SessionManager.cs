using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using AstraAgent.Service.Sessions;

namespace AstraAgent.Service.Remediation;

/// <summary>Acts on ONE logon session: lock it, sign it out, or put a message on it.
///
/// All three run in the elevated service and take the Windows session id as a parameter,
/// which is the whole point. The tray lives inside a single user's session and can only ever
/// act on that one; on a machine with two people signed in — the case these exist for — it
/// would act on whichever of them happened to be running it. LocalSystem can reach across
/// sessions, so the caller gets to say which.
///
/// Independent guardrails, not trusting the backend's:
///   * session 0 is refused outright — it is the services session, has no desktop, and an
///     action aimed at it does nothing while looking like it worked;
///   * the session must currently exist and be Active or Disconnected, so a stale id from a
///     portal page rendered ten minutes ago cannot land on whoever holds that id now.</summary>
public static class SessionManager
{
    public static (bool, string) Lock(string? sessionIdRaw)
    {
        var (ok, sessionId, refusal) = Resolve(sessionIdRaw);
        if (!ok) return (false, refusal!);

        // The real thing first: run LockWorkStation inside the session, which is byte for
        // byte what Win+L does — the desktop locks, everything keeps running, and the person
        // comes back to their own lock screen with their name on it.
        var (launched, why) = SessionProcessLauncher.Run(
            sessionId, "rundll32.exe", "user32.dll,LockWorkStation");
        if (launched)
            return (true, $"Session {sessionId} locked. The user's work is still open and running.");

        // Fallback: disconnect. Not the same thing and worth being honest about — the session
        // detaches instead of locking, so the console drops to the sign-in screen rather than
        // the user's own lock screen. What matters is preserved either way: nothing closes,
        // nothing is lost, and getting back in still needs the password.
        if (WtsNative.WTSDisconnectSession(IntPtr.Zero, sessionId, false))
            return (true, $"Session {sessionId} disconnected (the lock screen could not be "
                        + $"invoked directly: {why}). The user's work is still open and running; "
                        + "they sign back in to return to it.");

        return (false, $"Could not lock session {sessionId}: {why}");
    }

    public static (bool, string) Logoff(string? sessionIdRaw)
    {
        var (ok, sessionId, refusal) = Resolve(sessionIdRaw);
        if (!ok) return (false, refusal!);

        // bWait: false. Windows tears a session down over seconds to minutes depending on
        // what is open; blocking here would hold the remediation worker — and therefore every
        // other queued action on this device — for the duration.
        if (!WtsNative.WTSLogoffSession(IntPtr.Zero, sessionId, false))
            return (false,
                $"Windows refused to sign out session {sessionId} (error "
                + $"{Marshal.GetLastWin32Error()}).");
        return (true, $"Session {sessionId} is being signed out. Anything unsaved in it is gone — "
                    + "Windows does not prompt when nobody is at the keyboard to answer.");
    }

    public static (bool, string) SendMessage(string? sessionIdRaw, string? message)
    {
        var (ok, sessionId, refusal) = Resolve(sessionIdRaw);
        if (!ok) return (false, refusal!);

        var text = (message ?? string.Empty).Trim();
        if (text.Length == 0) return (false, "There was no message to show.");
        if (text.Length > 1000) text = text[..1000];

        const string title = "Message from IT";
        // bWait: false — this returns as soon as the box is on screen. Waiting would mean the
        // remediation only completes when the person clicks OK, so a message sent to an empty
        // desk would sit in the queue as "running" until somebody came back from lunch, and
        // every other action for that device would sit behind it.
        var shown = WtsNative.WTSSendMessage(
            IntPtr.Zero, sessionId,
            title, title.Length * 2,
            text, text.Length * 2,
            0 /* MB_OK */, 0 /* no timeout */, out _, false);

        if (!shown)
            return (false,
                $"Could not show the message on session {sessionId} (error "
                + $"{Marshal.GetLastWin32Error()}).");
        return (true, $"Message shown on session {sessionId}. It is one-way — there is no reply "
                    + "for ASTRA to collect.");
    }

    /// <summary>The part of the check that does not need a live machine: is this a session id
    /// at all, and is it one it can ever be right to act on?
    ///
    /// Split out from Resolve so it can be tested. The half that needs Windows — does this
    /// session exist right now — cannot be, and the half that decides what is refusable can.
    /// Returns the parsed id, or a refusal explaining itself.</summary>
    internal static (int? SessionId, string? Refusal) ParseSessionId(string? raw)
    {
        var text = (raw ?? string.Empty).Trim();
        if (text.Length == 0 || !int.TryParse(text, out var sessionId) || sessionId < 0)
            return (null, "No Windows session id was given.");
        if (sessionId == 0)
            return (null, "Session 0 is the Windows services session — nobody is signed into it.");
        return (sessionId, null);
    }

    /// <summary>Parses and validates the session id against the machine's live session list.</summary>
    private static (bool Ok, int SessionId, string? Refusal) Resolve(string? raw)
    {
        var (parsed, refused) = ParseSessionId(raw);
        if (parsed is null) return (false, 0, refused!);
        var sessionId = parsed.Value;

        var live = new List<WtsNative.WTS_SESSION_INFO>(WtsNative.Enumerate());
        foreach (var s in live)
        {
            if (s.SessionId != sessionId) continue;
            if (s.State != WtsNative.WtsActive && s.State != WtsNative.WtsDisconnected)
                return (false, 0, $"Session {sessionId} is not an interactive session.");
            return (true, sessionId, null);
        }
        // The common cause is a portal page a few minutes stale — the person signed out. Say
        // that, rather than an error code, because the answer is to refresh and look again.
        return (false, 0,
            $"Session {sessionId} no longer exists on this machine — the user has signed out "
            + "or the session was already ended.");
    }
}
