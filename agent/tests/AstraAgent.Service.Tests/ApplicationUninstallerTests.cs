using AstraAgent.Service.Remediation;
using Xunit;

namespace AstraAgent.Service.Tests;

/// <summary>The decision to tear software off a machine, tested directly.
///
/// The uninstall itself needs a real Windows install and cannot be exercised here, so the
/// code is arranged to put the whole judgement in one pure function: given what the registry
/// recorded, what would we run — and when would we decline? That is the part that decides
/// whether a machine is left alone or altered, and it is the part these tests hold.</summary>
public class ApplicationUninstallerTests
{
    [Fact]
    public void An_msi_is_uninstalled_quietly_by_product_code()
    {
        var (plan, refusal) = ApplicationUninstaller.PlanFor(
            "7-Zip 23.01",
            @"MsiExec.exe /I{23170F69-40C1-2702-2301-000001000000}",
            null);

        Assert.Null(refusal);
        Assert.NotNull(plan);
        Assert.Equal("msiexec.exe", plan!.FileName);
        // /I means "install" — reusing the recorded string verbatim would REPAIR the product
        // rather than remove it. Only the product code is carried over.
        Assert.Equal(
            new[] { "/x", "{23170F69-40C1-2702-2301-000001000000}", "/qn", "/norestart" },
            plan.Arguments);
    }

    [Fact]
    public void An_msi_without_a_product_code_is_refused()
    {
        var (plan, refusal) = ApplicationUninstaller.PlanFor("Broken", "MsiExec.exe /I", null);
        Assert.Null(plan);
        Assert.Contains("product code", refusal);
    }

    [Fact]
    public void A_vendors_own_silent_command_is_used_as_given()
    {
        var (plan, refusal) = ApplicationUninstaller.PlanFor(
            "Notepad++",
            @"C:\Program Files\Notepad++\uninstall.exe",
            @"""C:\Program Files\Notepad++\uninstall.exe"" /S");

        Assert.Null(refusal);
        Assert.Equal(@"C:\Program Files\Notepad++\uninstall.exe", plan!.FileName);
        Assert.Equal(new[] { "/S" }, plan.Arguments);
    }

    [Fact]
    public void Chrome_gets_the_switch_that_stops_it_asking()
    {
        // Chrome publishes no QuietUninstallString, and its recorded command opens a
        // confirmation dialog. In session 0 that dialog is invisible and the task would hang
        // until it timed out — which is precisely the case this feature exists for.
        var (plan, refusal) = ApplicationUninstaller.PlanFor(
            "Google Chrome",
            @"""C:\Program Files\Google\Chrome\Application\138.0.7204.51\Installer\setup.exe"" --uninstall --system-level --verbose-logging",
            null);

        Assert.Null(refusal);
        Assert.EndsWith(@"Installer\setup.exe", plan!.FileName);
        Assert.Contains("--uninstall", plan.Arguments);
        Assert.Contains("--system-level", plan.Arguments);
        Assert.Contains("--force-uninstall", plan.Arguments);
    }

    [Fact]
    public void A_switch_already_present_is_not_added_twice()
    {
        var (plan, _) = ApplicationUninstaller.PlanFor(
            "Google Chrome",
            @"""C:\setup.exe"" --uninstall --force-uninstall",
            null);

        Assert.Single(plan!.Arguments, a => a == "--force-uninstall");
    }

    [Fact]
    public void An_installer_that_would_open_a_window_is_refused_not_run()
    {
        // The whole point. An interactive uninstaller started as LocalSystem waits forever on
        // a prompt nobody can see, and the administrator is left staring at a task that never
        // finishes. Saying so is more useful than appearing to work.
        var (plan, refusal) = ApplicationUninstaller.PlanFor(
            "Some Legacy Tool",
            @"C:\Program Files\Legacy\unins000.exe",
            null);

        Assert.Null(plan);
        Assert.Contains("no silent uninstall", refusal);
        Assert.Contains("nobody could answer", refusal);
    }

    [Fact]
    public void An_application_recording_no_uninstall_command_is_refused()
    {
        var (plan, refusal) = ApplicationUninstaller.PlanFor("Ghost", null, null);
        Assert.Null(plan);
        Assert.Contains("no uninstall command", refusal);
    }

    [Theory]
    [InlineData(@"""C:\Program Files\App\u.exe"" /S", @"C:\Program Files\App\u.exe", "/S")]
    [InlineData(@"C:\Apps\u.exe /quiet", @"C:\Apps\u.exe", "/quiet")]
    public void A_quoted_path_with_spaces_survives_the_split(
        string command, string expectedFile, string expectedArg)
    {
        var (file, args) = ApplicationUninstaller.SplitCommandLine(command);
        Assert.Equal(expectedFile, file);
        Assert.Equal(new[] { expectedArg }, args);
    }

    [Fact]
    public void Arguments_are_split_for_argumentlist_never_handed_to_a_shell()
    {
        // Each argument must arrive as its own argv element. Passing the tail as one string
        // would leave quoting up to whatever parsed it next.
        var (file, args) = ApplicationUninstaller.SplitCommandLine(
            @"""C:\a b\setup.exe"" --uninstall --system-level --verbose-logging");
        Assert.Equal(@"C:\a b\setup.exe", file);
        Assert.Equal(new[] { "--uninstall", "--system-level", "--verbose-logging" }, args);
    }

    [Fact]
    public void A_nonzero_exit_is_success_when_the_app_is_actually_gone()
    {
        // The real failure this pins: Chrome's uninstaller ran from the SYSTEM account,
        // returned 19 over a cosmetic shortcut-cleanup error, and removed Chrome anyway —
        // and ASTRA called it a failure and showed the operator an error. The registry, not
        // the exit code, decides.
        var (ok, output) = ApplicationUninstaller.Verdict(
            "Google Chrome", "Chrome-style silent uninstall", exitCode: 19,
            stillInstalled: false, errorText: "Could not get application shortcuts location.");
        Assert.True(ok);
        Assert.Contains("Uninstalled Google Chrome", output);
    }

    [Fact]
    public void A_nonzero_exit_is_a_failure_when_the_app_remains()
    {
        var (ok, output) = ApplicationUninstaller.Verdict(
            "Some App", "vendor QuietUninstallString", exitCode: 1603,
            stillInstalled: true, errorText: "Fatal error during installation.");
        Assert.False(ok);
        Assert.Contains("1603", output);
        Assert.Contains("still", output);
    }

    [Fact]
    public void A_clean_exit_that_left_the_app_behind_is_reported_as_odd_not_success()
    {
        var (ok, output) = ApplicationUninstaller.Verdict(
            "Some App", "Windows Installer (/qn)", exitCode: 0,
            stillInstalled: true, errorText: "");
        Assert.False(ok);
        Assert.Contains("reported success", output);
    }

    [Fact]
    public void A_restart_needed_exit_is_success_even_if_the_entry_lingers()
    {
        // 3010 means "removed, reboot to finish" — the registry stub can outlive the exit, so
        // a still-present entry here is expected, not a failure.
        var (ok, output) = ApplicationUninstaller.Verdict(
            "Some App", "Windows Installer (/qn)", exitCode: 3010,
            stillInstalled: true, errorText: "");
        Assert.True(ok);
        Assert.Contains("restart", output);
    }

    [Fact]
    public void The_elevated_service_now_accepts_the_action()
    {
        Assert.Contains("uninstall_application", SystemRemediationExecutor.SupportedActions);
    }

    [Fact]
    public void An_unknown_action_is_still_refused_by_the_elevated_service()
    {
        var (ok, output) = new SystemRemediationExecutor().Execute("format_disk");
        Assert.False(ok);
        Assert.Contains("not a system-context action", output);
    }
}
