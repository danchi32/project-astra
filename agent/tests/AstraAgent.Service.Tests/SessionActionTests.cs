using System;
using System.Linq;
using AstraAgent.Service.Remediation;
using AstraAgent.Service.Sessions;
using Xunit;

namespace AstraAgent.Service.Tests;

/// <summary>The session actions — lock, sign out, message, reset a password.
///
/// None of them can be run here: they need real logon sessions, a real SAM, and a desktop to
/// put a dialog on. So, as with the elevated repairs beside them, the DECISIONS are pure
/// functions and this is what holds those. The decisions are the half that matters — the
/// difference between "sign out session 7" and "sign out session 0", or between resetting
/// "olivia" and resetting whatever text arrived from the network.</summary>
public class SessionActionTests
{
    // ---- Which session ids may be acted on ------------------------------------------

    [Theory]
    [InlineData("1")]
    [InlineData("2")]
    [InlineData(" 7 ")]     // the portal sends a string; whitespace should not decide an outcome
    [InlineData("65535")]
    public void A_real_session_id_parses(string raw)
    {
        var (id, refusal) = SessionManager.ParseSessionId(raw);
        Assert.Null(refusal);
        Assert.NotNull(id);
    }

    [Fact]
    public void Session_zero_is_refused()
    {
        // Session 0 is where services live. It has no desktop and nobody is signed into it,
        // so every action aimed there does nothing — while reporting that it worked, which
        // is the part that would send a technician to the wrong desk.
        var (id, refusal) = SessionManager.ParseSessionId("0");
        Assert.Null(id);
        Assert.Contains("services session", refusal);
    }

    [Theory]
    [InlineData(null)]
    [InlineData("")]
    [InlineData("   ")]
    [InlineData("two")]
    [InlineData("-1")]
    [InlineData("2; shutdown")]   // it is a string on the wire, so it gets treated like one
    public void Anything_that_is_not_a_session_id_is_refused(string? raw)
    {
        var (id, refusal) = SessionManager.ParseSessionId(raw);
        Assert.Null(id);
        Assert.False(string.IsNullOrEmpty(refusal));
    }

    // ---- Console vs RDP -------------------------------------------------------------
    //
    // Not cosmetic. "Disconnected console" is a locked or switched-away desktop; "disconnected
    // RDP" is somebody who closed a remote window and left their work running. A technician
    // treats those differently, so the column has to be right.

    [Theory]
    [InlineData("Console", null, "console")]
    [InlineData("console", null, "console")]
    [InlineData("RDP-Tcp#3", "LAPTOP-7", "rdp")]
    [InlineData("ICA-tcp#2", "THINCLIENT", "rdp")]
    public void The_station_name_names_the_connection(string station, string? client, string expected)
        => Assert.Equal(expected, WtsNative.ConnectionKind(station, client));

    [Fact]
    public void An_unrecognised_station_with_a_remote_client_is_remote()
    {
        // Third-party terminal-services stacks rename the WinStation. A session that calls
        // itself nothing we know but has a client machine attached IS remote, whatever it is
        // called, and guessing "console" there would hide exactly the sessions worth seeing.
        Assert.Equal("rdp", WtsNative.ConnectionKind("XYZ-42", "JUMPBOX-2"));
        Assert.Equal("console", WtsNative.ConnectionKind("XYZ-42", null));
        Assert.Equal("console", WtsNative.ConnectionKind(null, null));
    }

    // ---- Windows' zero timestamps ---------------------------------------------------

    [Fact]
    public void A_zero_filetime_is_not_a_date()
    {
        // Local console sessions frequently report no LastInputTime at all. Converting the
        // zero anyway yields 1601-01-01, which travels intact to a portal that then renders
        // "signed in 424 years ago" — so it has to become null here, at the boundary.
        Assert.Null(WtsNative.FromFileTime(0));
        Assert.Null(WtsNative.FromFileTime(-1));
        Assert.NotNull(WtsNative.FromFileTime(DateTimeOffset.UtcNow.ToFileTime()));
    }

    // ---- Whose password may be reset ------------------------------------------------

    [Theory]
    [InlineData("olivia", "olivia")]
    [InlineData("ACME\\olivia", "olivia")]      // what a session actually reports
    [InlineData("  ACME\\Olivia  ", "Olivia")]
    [InlineData("first.last", "first.last")]
    public void A_domain_qualified_name_resolves_to_the_account(string given, string expected)
    {
        var (name, refusal) = LocalPasswordReset.NormalizeName(given);
        Assert.Null(refusal);
        Assert.Equal(expected, name);
    }

    [Theory]
    [InlineData(null)]
    [InlineData("")]
    [InlineData("olivia@acme.com")]      // an Entra UPN, not a local account
    [InlineData("olivia\"; net user")]
    [InlineData("../../administrator")]
    [InlineData("-olivia")]              // Windows account names cannot start with punctuation
    public void A_name_that_is_not_an_account_name_is_refused(string? given)
    {
        var (name, refusal) = LocalPasswordReset.NormalizeName(given);
        Assert.Null(name);
        Assert.False(string.IsNullOrEmpty(refusal));
    }

    // ---- The generated password -----------------------------------------------------

    [Fact]
    public void The_generated_password_meets_windows_complexity()
    {
        // Complexity is not the interesting property on its own — it is that the password has
        // to satisfy the policy on EVERY machine in a fleet without anyone tuning it, because
        // a rejected password means a support call that this feature existed to prevent.
        for (var i = 0; i < 50; i++)
        {
            var password = LocalPasswordReset.GeneratePassword();
            Assert.Equal(16, password.Length);
            Assert.Contains(password, char.IsLower);
            Assert.Contains(password, char.IsUpper);
            Assert.Contains(password, char.IsDigit);
            Assert.Contains(password, c => !char.IsLetterOrDigit(c));
        }
    }

    [Fact]
    public void The_generated_password_can_be_read_down_a_phone()
    {
        // Its entire job is to be read aloud to somebody locked out of their machine. A
        // password containing 0/O or 1/l/I generates the second support call this was meant
        // to avoid, so the ambiguous glyphs are excluded from the alphabet.
        for (var i = 0; i < 50; i++)
            Assert.DoesNotContain(LocalPasswordReset.GeneratePassword(), "0O1lI".Contains);
    }

    [Fact]
    public void Two_generated_passwords_are_not_the_same()
    {
        var generated = Enumerable.Range(0, 100)
            .Select(_ => LocalPasswordReset.GeneratePassword())
            .ToHashSet();
        Assert.Equal(100, generated.Count);
    }

    // ---- The allowlist --------------------------------------------------------------

    [Theory]
    [InlineData("lock_session")]
    [InlineData("logoff_session")]
    [InlineData("message_session")]
    [InlineData("reset_local_password")]
    public void The_elevated_service_claims_the_session_actions(string actionId)
    {
        // They live in the SERVICE, not the Tray, and that is structural rather than
        // incidental: the Tray runs inside one user's session and can only reach that one.
        // On a machine with two people signed in — the case these exist for — it would act
        // on whichever of them happened to be running it.
        Assert.Contains(actionId, SystemRemediationExecutor.SupportedActions);
        Assert.DoesNotContain(actionId, AstraAgent.Tray.Remediation.RemediationExecutor.SupportedActions);
    }

    [Fact]
    public void An_unknown_session_action_is_refused()
    {
        var (ok, output) = new SystemRemediationExecutor().Execute("shadow_session");
        Assert.False(ok);
        Assert.Contains("not a system-context action", output);
    }
}
