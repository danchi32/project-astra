using AstraAgent.Service.Remediation;
using Xunit;

namespace AstraAgent.Service.Tests;

public class LocalAccountCreatorTests
{
    [Theory]
    [InlineData("asha", null)]
    [InlineData("asha.sharma", null)]
    [InlineData("Front Desk 2", null)]
    [InlineData("ACME\asha", "can't be a local account name")]      // never a domain account
    [InlineData("a-name-longer-than-20c", "can't be a local account name")]
    [InlineData("bad;name", "can't be a local account name")]
    [InlineData("", "can't be a local account name")]
    [InlineData(" trailing-dot.", null)]
    public void Refusal_AllowsOnlyNamesWindowsAccepts(string name, string? expected)
    {
        var refusal = LocalAccountCreator.Refusal(name, "Asha Sharma");
        if (expected is null) Assert.Null(refusal);
        else Assert.Contains(expected, refusal);
    }

    [Fact]
    public void Executor_AdvertisesTheAction()
        => Assert.Contains("create_local_user", SystemRemediationExecutor.SupportedActions);

    [Fact]
    public void WellKnownGroupSids_ResolveOnThisMachine()
    {
        // Membership is set by SID and translated locally, so it works on non-English Windows.
        foreach (var sid in new[] { LocalAccountCreator.UsersSid, LocalAccountCreator.AdministratorsSid })
        {
            var name = new System.Security.Principal.SecurityIdentifier(sid)
                .Translate(typeof(System.Security.Principal.NTAccount)).Value;
            Assert.False(string.IsNullOrWhiteSpace(name));
        }
    }
}

public class LocalAccountListTests
{
    [Fact]
    public void List_ReadsThisMachinesLocalAccounts()
    {
        // Every Windows install has the built-in Administrator and Guest accounts (often
        // disabled), so a working reader returns at least those, flagged as built-in.
        var accounts = LocalAccountManager.List();
        Assert.NotNull(accounts);
        Assert.Contains(accounts!, a => a.BuiltIn);
        Assert.All(accounts!, a => Assert.False(string.IsNullOrWhiteSpace(a.Name)));
    }

    [Theory]
    [InlineData("bad;name")]
    [InlineData("")]
    public void SetAdmin_RefusesInvalidNamesWithoutTouchingTheMachine(string name)
    {
        var (ok, msg) = LocalAccountManager.SetAdmin(name, "true");
        Assert.False(ok);
        Assert.Contains("not a valid local account name", msg);
    }

    [Fact]
    public void Executor_AdvertisesAdminToggle()
        => Assert.Contains("set_local_admin", SystemRemediationExecutor.SupportedActions);
}
