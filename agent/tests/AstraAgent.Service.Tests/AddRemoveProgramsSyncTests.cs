using AstraAgent.Service.Update;
using Xunit;

namespace AstraAgent.Service.Tests;

/// <summary>Keeping Control Panel's entry honest after an auto-update.
///
/// The registry write itself is three lines and needs a real machine; the judgement is the
/// part worth holding, and it is entirely about knowing when to do NOTHING. Writing on every
/// start would churn the registry, and writing an icon over one that works would overrule the
/// installer for no reason.</summary>
public class AddRemoveProgramsSyncTests
{
    private const string Ico = @"C:\Program Files\Astra\astra.ico";
    private const string Tray = @"C:\Program Files\Astra\Tray\AstraAgent.Tray.exe";

    [Fact]
    public void A_stale_version_is_corrected()
    {
        // The reported case: installed at 0.8.2, auto-updated to 0.8.8, Control Panel still
        // saying 0.8.2 while the portal said 0.8.8. Both were "right", which is why nobody
        // could tell which to believe.
        var repair = AddRemoveProgramsSync.Plan("0.8.8", "0.8.2", Ico, true, Ico);

        Assert.Equal("0.8.8", repair.DisplayVersion);
        Assert.Null(repair.DisplayIcon);   // this one was fine — leave it
    }

    [Fact]
    public void A_matching_version_is_left_alone()
    {
        // This runs on every service start. Rewriting the same value each time would churn
        // the registry and make any audit of what actually changed worthless.
        var repair = AddRemoveProgramsSync.Plan("0.9.0", "0.9.0", Ico, true, Ico);

        Assert.True(repair.IsEmpty);
    }

    [Fact]
    public void A_missing_icon_is_repaired()
    {
        // UninstallDisplayIcon arrived in 0.8.3, so an entry written by an earlier installer
        // has no DisplayIcon at all and Windows draws a blank page. No update could ever fix
        // it, because no update touched the key.
        var repair = AddRemoveProgramsSync.Plan("0.9.0", "0.9.0", null, false, Tray);

        Assert.Null(repair.DisplayVersion);
        Assert.Equal(Tray, repair.DisplayIcon);
    }

    [Fact]
    public void An_icon_pointing_at_a_file_that_is_gone_is_repaired()
    {
        var repair = AddRemoveProgramsSync.Plan(
            "0.9.0", "0.9.0", @"C:\Program Files\Astra\astra.ico", recordedIconExists: false,
            iconCandidate: Tray);

        Assert.Equal(Tray, repair.DisplayIcon);
    }

    [Fact]
    public void A_working_icon_is_never_overruled()
    {
        // It was the installer's choice and it resolves. Preferring our own candidate would
        // be changing something that works, on every machine, for no visible gain.
        var repair = AddRemoveProgramsSync.Plan("0.9.0", "0.9.0", Ico, true, Tray);

        Assert.Null(repair.DisplayIcon);
    }

    [Fact]
    public void Nothing_is_written_when_no_icon_exists_on_the_machine()
    {
        // Pointing DisplayIcon at a path that isn't there swaps a blank icon for a broken one.
        var repair = AddRemoveProgramsSync.Plan("0.9.0", "0.9.0", null, false, iconCandidate: null);

        Assert.True(repair.IsEmpty);
    }

    [Fact]
    public void A_build_that_lost_its_version_never_overwrites_a_real_one()
    {
        // AgentVersion falls back to 0.0.0 when the assembly carries no version. That value is
        // deliberately unusable everywhere else — it must not be allowed to stamp itself over
        // a correct number here either.
        var repair = AddRemoveProgramsSync.Plan("0.0.0", "0.8.8", Ico, true, Ico);

        Assert.Null(repair.DisplayVersion);
    }

    [Fact]
    public void An_entry_with_no_recorded_version_gets_one()
    {
        var repair = AddRemoveProgramsSync.Plan("0.9.0", null, Ico, true, Ico);

        Assert.Equal("0.9.0", repair.DisplayVersion);
    }

    [Fact]
    public void Both_are_repaired_together_when_both_are_wrong()
    {
        // A device installed at 0.8.2 and updated over the air: stale version AND no icon.
        var repair = AddRemoveProgramsSync.Plan("0.9.0", "0.8.2", null, false, Tray);

        Assert.Equal("0.9.0", repair.DisplayVersion);
        Assert.Equal(Tray, repair.DisplayIcon);
        Assert.False(repair.IsEmpty);
    }
}
