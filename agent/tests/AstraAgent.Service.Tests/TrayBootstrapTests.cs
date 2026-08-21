using AstraAgent.Tray.Update;
using Xunit;

namespace AstraAgent.Service.Tests;

public class TrayBootstrapTests
{
    [Fact]
    public void NoLiveCopy_AlwaysReseeds()
        => Assert.True(TrayBootstrap.NeedsReseed("0.1.0", "0.0.0", liveDllExists: false));

    [Fact]
    public void NewerSeed_Reseeds()
        => Assert.True(TrayBootstrap.NeedsReseed("0.2.0", "0.1.0", liveDllExists: true));

    [Fact]
    public void EqualVersion_DoesNotReseed()
        => Assert.False(TrayBootstrap.NeedsReseed("0.2.0", "0.2.0", liveDllExists: true));

    [Fact]
    public void OlderSeed_DoesNotClobberSelfUpdatedLiveCopy()
    {
        // The live copy self-updated to 0.4.0; a stale 0.2.0 seed must NOT overwrite it.
        Assert.False(TrayBootstrap.NeedsReseed("0.2.0", "0.4.0", liveDllExists: true));
    }
}

public class TrayReseedAfterServiceUpdateTests
{
    /// <summary>The exact fleet state on 2026-08-21: every tray sat at 0.8.2 (the version its
    /// installer wrote) while the service had climbed to 0.8.7, because nothing had ever
    /// refreshed the seed. Once a service update mirrors the release's tray\ payload into the
    /// seed, the next logon must re-seed the live copy — this is the step that actually puts the
    /// new tray in front of the user, so pin it.</summary>
    [Theory]
    [InlineData("0.8.8", "0.8.2", true)]    // seed refreshed by the update — must re-seed
    [InlineData("0.8.8", "0.8.7", true)]    // one release behind — must re-seed
    [InlineData("0.8.8", "0.8.8", false)]   // already current — must not churn
    [InlineData("0.8.2", "0.8.8", false)]   // never clobber a newer live copy with an older seed
    public void SeedRefreshedByAServiceUpdate_ReSeedsTheLiveCopy(
        string seed, string live, bool expected)
        => Assert.Equal(expected, TrayBootstrap.NeedsReseed(seed, live, liveDllExists: true));
}
