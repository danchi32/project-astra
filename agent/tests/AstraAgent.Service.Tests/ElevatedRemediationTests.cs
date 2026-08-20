using System.Linq;
using AstraAgent.Service.Remediation;
using AstraAgent.Tray.Remediation;
using Xunit;

namespace AstraAgent.Service.Tests;

/// <summary>The elevated repairs — service restarts, Office repair, network recovery.
///
/// None of them can be run here: they stop Windows services, drop the network, and drive
/// Office's installer. So each is arranged the way ApplicationUninstaller already is, with
/// the decision — what would we do, and when would we decline — in a pure function, and that
/// is what these tests hold. It is also the half that matters: the decision is what stands
/// between "restart the print spooler" and "restart LSASS".</summary>
public class ElevatedRemediationTests
{
    // ---- Which services may be restarted --------------------------------------------
    //
    // The service name arrives as a PARAMETER, unlike every other elevated action, where the
    // target is fixed by the action id. The allowlist is the whole of the safety story.

    [Theory]
    [InlineData("Spooler")]
    [InlineData("spooler")]              // service names are case-insensitive in Windows
    [InlineData("Print Spooler")]        // what a person (or the model) would actually say
    [InlineData("wuauserv")]
    [InlineData("Windows Search")]
    public void Allowlisted_services_resolve(string requested)
    {
        var (name, label, refusal) = ServiceRestarter.Resolve(requested);
        Assert.Null(refusal);
        Assert.False(string.IsNullOrEmpty(name));
        Assert.False(string.IsNullOrEmpty(label));
    }

    [Theory]
    [InlineData("LSASS")]                // taking this down bluescreens the machine
    [InlineData("RpcSs")]                // half of Windows depends on it
    [InlineData("TrustedInstaller")]
    [InlineData("MsMpSvc")]              // never let a fix disable the antivirus
    [InlineData("Sense")]                // Defender for Endpoint
    public void Critical_services_are_refused(string requested)
    {
        var (name, _, refusal) = ServiceRestarter.Resolve(requested);
        Assert.Null(name);
        Assert.Contains("not a service this agent may restart", refusal);
    }

    [Fact]
    public void The_agent_refuses_to_restart_itself()
    {
        // Restarting AstraAgent would kill the process running the remediation, so the task
        // could never report a result — it would look like a hang, forever.
        var (name, _, refusal) = ServiceRestarter.Resolve("AstraAgent");
        Assert.Null(name);
        Assert.NotNull(refusal);
    }

    [Fact]
    public void A_refusal_names_what_is_allowed()
    {
        // A bare "no" leaves the reasoning engine to guess again next turn.
        var (_, _, refusal) = ServiceRestarter.Resolve("Bluetooth Support Service");
        Assert.Contains("Print Spooler", refusal);
    }

    [Theory]
    [InlineData(null)]
    [InlineData("")]
    [InlineData("   ")]
    public void A_missing_service_name_is_refused(string? requested)
    {
        var (name, _, refusal) = ServiceRestarter.Resolve(requested);
        Assert.Null(name);
        Assert.NotNull(refusal);
    }

    // ---- Opening Office's repair ------------------------------------------------------
    //
    // The command is READ from the registry, never composed, and these are the real strings
    // from the machine where this was diagnosed. The first implementation built its own
    // command with two arguments Control Panel does not pass — RepairType=QuickRepair and
    // DisplayLevel=False — and nothing happened, from any context. Parsing what Windows
    // recorded is the whole fix, so parsing it correctly is what these hold.

    private const string M365Modify =
        @"""C:\Program Files\Common Files\Microsoft Shared\ClickToRun\OfficeClickToRun.exe"" "
        + "scenario=repair platform=x64 culture=en-us";

    [Fact]
    public void The_office_modify_command_is_split_into_exe_and_arguments()
    {
        var (exe, args) = OfficeRepairLauncher.ParseModifyPath(M365Modify);

        Assert.Equal(@"C:\Program Files\Common Files\Microsoft Shared\ClickToRun\OfficeClickToRun.exe", exe);
        Assert.Equal(new[] { "scenario=repair", "platform=x64", "culture=en-us" }, args);
        // Nothing added. The two arguments that were invented last time are the reason this
        // assertion is exact rather than a Contains.
        Assert.DoesNotContain("DisplayLevel=False", args);
        Assert.DoesNotContain("RepairType=QuickRepair", args);
    }

    [Theory]
    [InlineData("MsiExec.exe /X{90160000-008C-0000-1000-0000000FF1CE}")]  // an Office component
    [InlineData("")]
    [InlineData(null)]
    [InlineData(@"C:\no\quotes\here.exe scenario=repair")]
    public void Anything_that_is_not_a_quoted_executable_is_refused(string? modifyPath)
    {
        // An MSI product code here would uninstall a component instead of repairing Office.
        var (exe, _) = OfficeRepairLauncher.ParseModifyPath(modifyPath);
        Assert.Null(exe);
    }

    [Fact]
    public void The_office_suite_is_told_apart_from_its_add_ins()
    {
        // A real machine carries several entries matching "Office". Repairing the wrong one
        // does nothing at best.
        Assert.True(OfficeRepairLauncher.IsOfficeSuite(
            "Microsoft 365 Apps for business - en-us", M365Modify));

        Assert.False(OfficeRepairLauncher.IsOfficeSuite(
            "Office 16 Click-to-Run Extensibility Component",
            "MsiExec.exe /X{90160000-008C-0000-1000-0000000FF1CE}"));
        Assert.False(OfficeRepairLauncher.IsOfficeSuite(
            "Microsoft Teams Meeting Add-in for Microsoft Office",
            "MsiExec.exe /I{A7AB73A3-CB10-4AA5-9D38-6AEFFBDE4C91}"));
        Assert.False(OfficeRepairLauncher.IsOfficeSuite("Google Chrome", M365Modify));
    }

    // ---- Which network adapter to bounce ----------------------------------------------

    private static NetworkRemediation.AdapterInfo Nic(
        string name, bool up = true, bool gateway = false, bool physical = true)
        => new(name, name + " description", up, gateway, physical);

    [Fact]
    public void The_routed_adapter_is_preferred_over_idle_ones()
    {
        // "The internet is not working" means the adapter carrying traffic. Bouncing an idle
        // VPN or Bluetooth interface fixes nothing and still drops the link.
        var (names, refusal) = NetworkRemediation.Choose(new[]
        {
            Nic("Bluetooth Network Connection"),
            Nic("Wi-Fi", gateway: true),
            Nic("Ethernet 2"),
        });

        Assert.Null(refusal);
        Assert.Equal(new[] { "Wi-Fi" }, names.ToArray());
    }

    [Fact]
    public void With_no_gateway_every_active_adapter_is_tried()
    {
        // No gateway anywhere is itself the common symptom — DHCP failed — so this is exactly
        // when a bounce is wanted, not a reason to decline.
        var (names, refusal) = NetworkRemediation.Choose(new[] { Nic("Wi-Fi"), Nic("Ethernet") });

        Assert.Null(refusal);
        Assert.Equal(new[] { "Wi-Fi", "Ethernet" }, names.ToArray());
    }

    [Fact]
    public void Loopback_and_tunnel_adapters_are_never_touched()
    {
        var (names, refusal) = NetworkRemediation.Choose(new[]
        {
            Nic("Loopback Pseudo-Interface 1", physical: false, gateway: true),
            Nic("Ethernet", gateway: true),
        });

        Assert.Null(refusal);
        Assert.Equal(new[] { "Ethernet" }, names.ToArray());
    }

    [Fact]
    public void A_down_adapter_is_not_bounced()
    {
        var (names, refusal) = NetworkRemediation.Choose(new[] { Nic("Ethernet", up: false) });

        Assert.Empty(names);
        Assert.Contains("No active network adapter", refusal);
    }
}
