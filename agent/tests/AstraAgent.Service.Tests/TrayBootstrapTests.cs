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
