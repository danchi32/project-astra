using System;
using System.Collections.Generic;
using System.Linq;
using System.ServiceProcess;

namespace AstraAgent.Service.Remediation;

/// <summary>Restarts a Windows service — but only one from a fixed allowlist.
///
/// "Restart a service" is the most dangerous-sounding action the agent exposes, because the
/// service name arrives as a PARAMETER rather than being implied by the action id. An
/// allowlist is what keeps that from mattering: the reasoning engine can ask for anything,
/// and only these fifteen names are ever acted on. Restarting the wrong service — LSASS,
/// RpcSs, or this agent itself — takes the machine down or kills the process mid-remediation,
/// so safety here comes from what is absent from the list, not from validation of the input.
///
/// The names below are the ones IT actually restarts to fix a complaint: printing, audio,
/// name resolution, Windows Update, search. Anything outside that is refused with an
/// explanation rather than attempted.</summary>
public static class ServiceRestarter
{
    /// <summary>Service key name -> the name a person would recognise. Both are accepted, so
    /// "Print Spooler" and "Spooler" both resolve.</summary>
    private static readonly IReadOnlyDictionary<string, string> Allowed =
        new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
        {
            ["Spooler"] = "Print Spooler",
            ["PrintNotify"] = "Printer Extensions and Notifications",
            ["Audiosrv"] = "Windows Audio",
            ["AudioEndpointBuilder"] = "Windows Audio Endpoint Builder",
            ["Dnscache"] = "DNS Client",
            ["Dhcp"] = "DHCP Client",
            ["wuauserv"] = "Windows Update",
            ["BITS"] = "Background Intelligent Transfer Service",
            ["WSearch"] = "Windows Search",
            ["W32Time"] = "Windows Time",
            ["LanmanWorkstation"] = "Workstation",
            ["WlanSvc"] = "WLAN AutoConfig",
            ["Themes"] = "Themes",
            ["CryptSvc"] = "Cryptographic Services",
            ["SysMain"] = "SysMain",
        };

    private static readonly TimeSpan StateTimeout = TimeSpan.FromSeconds(45);

    /// <summary>Decides whether a requested service may be restarted, and under what key name.
    ///
    /// Pure, so the allowlist can be tested without a machine to break. Returns the canonical
    /// service name, or a refusal explaining what is allowed.</summary>
    public static (string? ServiceName, string? Label, string? Refusal) Resolve(string? requested)
    {
        var wanted = (requested ?? string.Empty).Trim();
        if (wanted.Length == 0)
            return (null, null, "No service was named.");

        foreach (var (name, label) in Allowed)
        {
            if (name.Equals(wanted, StringComparison.OrdinalIgnoreCase)
                || label.Equals(wanted, StringComparison.OrdinalIgnoreCase))
                return (name, label, null);
        }

        // Name what IS permitted: a bare refusal leaves the engine guessing, and it will guess
        // again next turn.
        var known = string.Join(", ", Allowed.Values.OrderBy(v => v, StringComparer.OrdinalIgnoreCase));
        return (null, null,
            $"'{wanted}' is not a service this agent may restart. Allowed: {known}.");
    }

    public static (bool Success, string Output) Restart(string? requested)
    {
        var (name, label, refusal) = Resolve(requested);
        if (refusal is not null) return (false, refusal);

        try
        {
            using var service = new ServiceController(name!);

            // Touching Status throws if the service does not exist on this edition of Windows
            // (WSearch and SysMain are both absent on some builds). Say which, rather than
            // surfacing a raw InvalidOperationException.
            ServiceControllerStatus status;
            try { status = service.Status; }
            catch (InvalidOperationException)
            {
                return (false, $"The {label} service is not installed on this PC.");
            }

            // Dependents must come down first or Stop() refuses — and they must come back up
            // afterwards, or fixing the printer would quietly break something else.
            var dependents = service.DependentServices
                .Where(d => d.Status != ServiceControllerStatus.Stopped)
                .ToList();

            foreach (var dependent in dependents)
            {
                dependent.Stop();
                dependent.WaitForStatus(ServiceControllerStatus.Stopped, StateTimeout);
            }

            if (status != ServiceControllerStatus.Stopped)
            {
                service.Stop();
                service.WaitForStatus(ServiceControllerStatus.Stopped, StateTimeout);
            }

            service.Start();
            service.WaitForStatus(ServiceControllerStatus.Running, StateTimeout);

            var restored = new List<string>();
            foreach (var dependent in dependents)
            {
                try
                {
                    dependent.Start();
                    dependent.WaitForStatus(ServiceControllerStatus.Running, StateTimeout);
                    restored.Add(dependent.DisplayName);
                }
                catch (Exception ex)
                {
                    // The service we were asked about is running; a dependent that did not come
                    // back is still a problem the person needs told about.
                    return (true,
                        $"Restarted {label}, but its dependent service '{dependent.DisplayName}' "
                        + $"did not come back up: {ex.Message}");
                }
            }

            service.Refresh();
            if (service.Status != ServiceControllerStatus.Running)
                return (false, $"{label} did not reach a running state (it is {service.Status}).");

            var msg = $"Restarted {label}.";
            if (restored.Count > 0)
                msg += $" Dependent services restarted with it: {string.Join(", ", restored)}.";
            return (true, msg);
        }
        catch (System.ServiceProcess.TimeoutException)
        {
            return (false,
                $"{label} did not stop or start within {StateTimeout.TotalSeconds:0} seconds. "
                + "It may be hung; a restart of the PC will clear it.");
        }
        catch (Exception ex)
        {
            return (false, $"Could not restart {label}: {ex.Message}");
        }
    }
}
