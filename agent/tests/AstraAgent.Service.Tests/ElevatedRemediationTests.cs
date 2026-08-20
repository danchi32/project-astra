using System.Linq;
using AstraAgent.Service.Remediation;
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

    // ---- Office repair ---------------------------------------------------------------

    [Fact]
    public void Office_repair_runs_a_silent_quick_repair()
    {
        var (plan, refusal) = OfficeRepair.PlanFor(@"C:\CTR\OfficeClickToRun.exe", "x64", "en-us");

        Assert.Null(refusal);
        Assert.Equal(@"C:\CTR\OfficeClickToRun.exe", plan!.FileName);
        Assert.Contains("scenario=Repair", plan.Arguments);
        Assert.Contains("RepairType=QuickRepair", plan.Arguments);
        // Session 0 has no desktop: a repair waiting on an invisible dialog would hang until
        // the timeout with nothing to show for it.
        Assert.Contains("DisplayLevel=False", plan.Arguments);
        Assert.Contains("platform=x64", plan.Arguments);
        Assert.Contains("culture=en-us", plan.Arguments);
    }

    [Fact]
    public void An_msi_office_install_is_refused_rather_than_guessed_at()
    {
        // Repairing MSI Office needs a product code, and the wrong one repairs — or removes —
        // a different product. Better to say so than to guess.
        var (plan, refusal) = OfficeRepair.PlanFor(null, "x64", "en-us");

        Assert.Null(plan);
        Assert.Contains("Click-to-Run", refusal);
        Assert.Contains("Settings", refusal);   // tells the admin where to repair it by hand
    }

    [Fact]
    public void Missing_registry_values_fall_back_rather_than_failing()
    {
        // Platform/culture are only hints to stop OfficeClickToRun prompting; an install that
        // did not record them is still repairable.
        var (plan, refusal) = OfficeRepair.PlanFor(@"C:\CTR\OfficeClickToRun.exe", null, null);

        Assert.Null(refusal);
        Assert.Contains("platform=x64", plan!.Arguments);
        Assert.Contains("culture=en-us", plan.Arguments);
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
