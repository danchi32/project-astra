using System.Security.AccessControl;
using System.Security.Principal;
using System.Text.Json;
using AstraAgent.Guard;
using AstraAgent.GuardHost;
using AstraAgent.Service.Api;
using AstraAgent.Service.Guard;
using Microsoft.Win32;
using Xunit;

namespace AstraAgent.Service.Tests;

/// <summary>
/// Phase 3 · D7 approvals on the PC: stored per Windows account where only that account can
/// read them, and honoured by the host only for that site, that channel, until that time.
/// Runs under a throwaway HKCU key, never HKLM.
/// </summary>
public sealed class GuardApprovalTests : IDisposable
{
    readonly string _sandbox = $@"Software\SavioTests\{Guid.NewGuid():N}";
    readonly RegistryKey _root;
    static readonly SecurityIdentifier Me = WindowsIdentity.GetCurrent().User!;

    public GuardApprovalTests() => _root = Registry.CurrentUser.CreateSubKey(_sandbox, writable: true);

    public void Dispose()
    {
        _root.Dispose();
        Registry.CurrentUser.DeleteSubKeyTree(_sandbox, false);
        using (var parent = Registry.CurrentUser.OpenSubKey(@"Software\SavioTests"))
            if (parent is { SubKeyCount: 0, ValueCount: 0 })
                try { Registry.CurrentUser.DeleteSubKey(@"Software\SavioTests", false); } catch (IOException) { }
    }

    // The real ACL, plus full control for the test account so the sandbox can be cleaned up
    // (an unelevated test is not "Administrators").
    GuardApprovalStore Store() => new(_root,
        account => account switch { @"PC\asha" => Me.Value, @"PC\ravi" => "S-1-5-21-1-2-3-1002", _ => null },
        sid =>
        {
            var s = GuardApprovalStore.ReadableBy(sid);
            s.AddAccessRule(new RegistryAccessRule(Me, RegistryRights.FullControl, AccessControlType.Allow));
            return s;
        });

    static AgentGuardApproval A(string user, string site, string channel = "paste", int minutes = 30) =>
        new(user, site, channel, DateTimeOffset.UtcNow.AddMinutes(minutes));

    string[]? Stored(string sid)
    {
        using var k = _root.OpenSubKey($@"{GuardApprovals.KeyPath}\{sid}");
        return k?.GetValue(GuardApprovals.ValueName) as string[];
    }

    [Fact]
    public void Each_account_gets_its_own_key_and_only_what_is_in_force()
    {
        Store().Write([A(@"PC\asha", "chatgpt.com"), A(@"PC\asha", "drive.google.com", "file"),
                       A(@"PC\ravi", "claude.ai"), A(@"GONE\nobody", "x.in")]);
        Assert.Equal(2, Stored(Me.Value)!.Length);
        Assert.Single(Stored("S-1-5-21-1-2-3-1002")!);
        using (var parent = _root.OpenSubKey(GuardApprovals.KeyPath)!)
            Assert.Equal(2, parent.SubKeyCount);                         // an account Windows cannot name is skipped

        Store().Write([A(@"PC\asha", "chatgpt.com")]);                   // ravi's ended
        Assert.Null(Stored("S-1-5-21-1-2-3-1002"));
        Assert.Single(Stored(Me.Value)!);

        Store().Write([]);
        Assert.Null(_root.OpenSubKey(GuardApprovals.KeyPath));
    }

    [Fact]
    public void Only_the_account_itself_can_read_its_approvals()
    {
        var rules = GuardApprovalStore.ReadableBy(Me);
        Assert.True(rules.AreAccessRulesProtected);                      // nothing inherited, so no "Users: read"
        var allowed = rules.GetAccessRules(true, false, typeof(SecurityIdentifier)).Cast<RegistryAccessRule>()
            .ToDictionary(r => (SecurityIdentifier)r.IdentityReference, r => r.RegistryRights);
        Assert.Equal(3, allowed.Count);
        Assert.Equal(RegistryRights.ReadKey, allowed[Me]);
        Assert.Equal(RegistryRights.FullControl, allowed[new SecurityIdentifier(WellKnownSidType.LocalSystemSid, null)]);
        Assert.DoesNotContain(new SecurityIdentifier(WellKnownSidType.BuiltinUsersSid, null), allowed.Keys);
    }

    [Fact]
    public async Task The_host_honours_an_approval_for_that_site_and_channel_until_it_ends()
    {
        var now = DateTimeOffset.UtcNow;
        var before = NativeHost.ReadApprovals;
        NativeHost.ReadApprovals = () => [GuardApprovals.Format("chatgpt.com", "paste", now.AddMinutes(10)),
                                          GuardApprovals.Format("claude.ai", "paste", now.AddMinutes(-1))];
        try
        {
            async Task<bool?> Ask(string site, string channel)
            {
                var r = await NativeHost.HandleAsync(JsonSerializer.SerializeToUtf8Bytes(new { type = "approved", site, channel }),
                                                     (_, _) => Task.FromResult(true), default);
                return r.Approved;
            }
            Assert.True(await Ask("chatgpt.com", "paste"));
            Assert.False(await Ask("chatgpt.com", "file"));             // another channel
            Assert.False(await Ask("chat.chatgpt.com", "paste"));       // another site, even a subdomain
            Assert.False(await Ask("claude.ai", "paste"));              // ended
            NativeHost.ReadApprovals = () => null;                      // nothing stored, or unreadable
            Assert.False(await Ask("chatgpt.com", "paste"));
        }
        finally { NativeHost.ReadApprovals = before; }
    }
}
