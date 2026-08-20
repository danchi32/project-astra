using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
using System.Net.NetworkInformation;

namespace AstraAgent.Service.Remediation;

/// <summary>The two network repairs that need elevation: bouncing an adapter, and resetting
/// the TCP/IP stack.
///
/// Both cut the machine off mid-run, including this agent's own connection. That is fine and
/// expected — the agent queues its results and reports once the link returns — but it does
/// mean an adapter that fails to come back is a serious outcome, not a warning. So the
/// adapter restart verifies the link is up again and says plainly when it is not, rather than
/// reporting success because the commands returned zero.</summary>
public static class NetworkRemediation
{
    /// <summary>What the chooser needs to know about an adapter. A plain record so the
    /// selection can be tested — NetworkInterface cannot be constructed in a test.</summary>
    public readonly record struct AdapterInfo(
        string Name, string Description, bool IsUp, bool HasGateway, bool IsPhysical);

    /// <summary>Picks which adapters to bounce.
    ///
    /// Prefers the ones actually carrying traffic (an assigned default gateway): when someone
    /// says "the internet is not working", that is the adapter they mean, and bouncing an idle
    /// Bluetooth or VPN interface would fix nothing while still dropping the link. Falls back
    /// to any up physical adapter when nothing has a gateway — which is itself a common
    /// symptom, DHCP having failed.</summary>
    public static (IReadOnlyList<string> Names, string? Refusal) Choose(IEnumerable<AdapterInfo> adapters)
    {
        var usable = adapters.Where(a => a.IsUp && a.IsPhysical).ToList();
        if (usable.Count == 0)
            return (Array.Empty<string>(),
                "No active network adapter was found to restart. The PC may already be offline, "
                + "or its adapter disabled in Device Manager.");

        var routed = usable.Where(a => a.HasGateway).ToList();
        return ((routed.Count > 0 ? routed : usable).Select(a => a.Name).ToList(), null);
    }

    private static IEnumerable<AdapterInfo> Enumerate()
    {
        foreach (var nic in NetworkInterface.GetAllNetworkInterfaces())
        {
            var physical = nic.NetworkInterfaceType != NetworkInterfaceType.Loopback
                        && nic.NetworkInterfaceType != NetworkInterfaceType.Tunnel;
            var gateway = false;
            try
            {
                gateway = nic.GetIPProperties().GatewayAddresses
                    .Any(g => g.Address is not null && !g.Address.ToString().StartsWith("0."));
            }
            catch { /* an adapter mid-teardown has no properties; treat as no gateway */ }

            yield return new AdapterInfo(
                nic.Name, nic.Description,
                nic.OperationalStatus == OperationalStatus.Up,
                gateway, physical);
        }
    }

    private static bool IsUpNow(string name)
        => NetworkInterface.GetAllNetworkInterfaces()
            .Any(n => n.Name == name && n.OperationalStatus == OperationalStatus.Up);

    public static (bool Success, string Output) RestartAdapter()
    {
        var (names, refusal) = Choose(Enumerate());
        if (refusal is not null) return (false, refusal);

        var restored = new List<string>();
        var stillDown = new List<string>();

        foreach (var name in names)
        {
            var (offOk, offErr) = Netsh("interface", "set", "interface", $"name={name}", "admin=disabled");
            if (!offOk)
                return (false, $"Could not disable '{name}': {offErr}");

            // Windows needs a moment between the two; enabling immediately can be ignored.
            System.Threading.Thread.Sleep(3000);

            var (onOk, onErr) = Netsh("interface", "set", "interface", $"name={name}", "admin=enabled");
            if (!onOk)
                // The adapter is DOWN and we could not bring it back. Nothing about this is a
                // partial success; the machine may now be offline.
                return (false,
                    $"'{name}' was disabled but could not be re-enabled: {onErr} "
                    + "Re-enable it from Network Connections, or restart the PC.");

            // Coming back and getting a DHCP lease takes a few seconds.
            var deadline = DateTime.UtcNow.AddSeconds(30);
            while (DateTime.UtcNow < deadline && !IsUpNow(name))
                System.Threading.Thread.Sleep(1000);

            (IsUpNow(name) ? restored : stillDown).Add(name);
        }

        if (restored.Count == 0)
            return (false,
                $"Restarted {string.Join(", ", stillDown)}, but the link did not come back up. "
                + "Check the cable or Wi-Fi, or restart the PC.");

        var msg = $"Restarted {string.Join(", ", restored)} — the adapter was disabled and "
                + "re-enabled, renewing its DHCP lease.";
        if (stillDown.Count > 0)
            msg += $" {string.Join(", ", stillDown)} did not come back up and needs checking.";
        return (true, msg);
    }

    public static (bool Success, string Output) ResetNetworkStack()
    {
        // Order matters: Winsock first, then the IP stack, matching Microsoft's own guidance.
        var (winsockOk, winsockErr) = Netsh("winsock", "reset");
        if (!winsockOk)
            return (false, $"Could not reset the Winsock catalog: {winsockErr}");

        var (ipOk, ipErr) = Netsh("int", "ip", "reset");
        if (!ipOk)
            // Winsock is already reset, so the machine is mid-change; a reboot still applies
            // what did land. Say that rather than implying nothing happened.
            return (false,
                $"Reset the Winsock catalog, but resetting the IP stack failed: {ipErr} "
                + "Restart the PC to apply the part that succeeded, then try again.");

        return (true,
            "Reset the TCP/IP stack and Winsock catalog. THIS NEEDS A RESTART — the old "
            + "configuration stays in effect until the PC is rebooted.");
    }

    private static (bool Ok, string Error) Netsh(params string[] args)
    {
        try
        {
            var psi = new ProcessStartInfo
            {
                FileName = "netsh.exe",
                UseShellExecute = false,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                CreateNoWindow = true,
            };
            // One argv element each — an adapter name can contain spaces, and building a
            // command string would let it be re-split.
            foreach (var arg in args) psi.ArgumentList.Add(arg);

            using var process = Process.Start(psi);
            if (process is null) return (false, "could not start netsh");

            var stdout = process.StandardOutput.ReadToEnd();
            var stderr = process.StandardError.ReadToEnd();
            process.WaitForExit(60000);

            if (process.ExitCode != 0)
            {
                var why = string.IsNullOrWhiteSpace(stderr) ? stdout : stderr;
                return (false, $"netsh exited with {process.ExitCode}. {why.Trim()}");
            }
            return (true, "");
        }
        catch (Exception ex)
        {
            return (false, ex.Message);
        }
    }
}
