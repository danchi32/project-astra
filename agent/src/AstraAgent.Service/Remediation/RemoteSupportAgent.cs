using System;
using Microsoft.Win32;

namespace AstraAgent.Service.Remediation;

/// <summary>Reads the remote-support agent's identity off this machine.
///
/// ASTRA does not own that agent's node id — the relay derives it from a certificate the
/// agent generates at install. But the agent writes it to a registry key whose NAME is the
/// service name ASTRA chose, so it is somewhere known, and the value is exactly the node id
/// the relay uses with a "node//" prefix. Verified against a live relay: the server's node
/// record was "node//" + this value, character for character.
///
/// This is why ASTRA reports it rather than matching on anything. A hostname or machine GUID
/// looks like it would do, and does not: two machines imaged from the same source report the
/// same GUID, and the fleet then shows two identical rows, one of them dead. ASTRA's own
/// machine_id stays the identity; this hangs beneath it, reported on every beat so that a
/// reinstalled agent corrects itself within a minute instead of pointing at a node that no
/// longer exists.
///
/// Everything here returns null rather than guessing. Null means "could not read" and the
/// backend leaves the last known value alone — the alternative is a transient read failure
/// erasing a working mapping and taking remote support down for that device.</summary>
public static class RemoteSupportAgent
{
    /// <summary>The service name ASTRA gives the remote-support agent, via the relay's
    /// agentCustomization. It is the registry key name, so the two must not drift: change
    /// it in the relay's config.json and this constant changes with it.</summary>
    private const string ServiceName = "AstraRemoteSupport";

    private static readonly string KeyPath = $@"SOFTWARE\Open Source\{ServiceName}";

    /// <summary>This device as the relay knows it, or null if the agent is not installed or
    /// has not registered yet. Already carries the "node//" prefix the relay uses, so the
    /// backend stores what it receives without reassembling anything.</summary>
    public static string? GetNodeId()
    {
        var raw = ReadValue("NodeId");
        // A key that exists with an empty value is an agent mid-install, not an answer.
        return string.IsNullOrWhiteSpace(raw) ? null : "node//" + raw.Trim();
    }

    /// <summary>The relay this agent is pointed at, so the backend can notice a device still
    /// talking to a decommissioned or wrong relay. Reported for the same reason os_version
    /// is: an install-day value that nobody re-checks is how a fleet drifts silently.</summary>
    public static string? GetServerUrl() => Blank(ReadValue("MeshServerUrl"));

    /// <summary>The device group the agent enrolled into. An agent in the wrong group is
    /// reachable by the wrong people, which is worth being able to see from the backend
    /// rather than only from the relay's own console.</summary>
    public static string? GetMeshId() => Blank(ReadValue("MeshId"));

    private static string? ReadValue(string name)
    {
        try
        {
            // 64-bit view explicitly. The Service runs as 64-bit, but saying so means this
            // keeps working if it is ever built for x86, where the default view would be the
            // WOW6432Node redirection and the key simply would not be there.
            using var baseKey = RegistryKey.OpenBaseKey(RegistryHive.LocalMachine, RegistryView.Registry64);
            using var key = baseKey.OpenSubKey(KeyPath, writable: false);
            return key?.GetValue(name) as string;
        }
        catch
        {
            return null;
        }
    }

    private static string? Blank(string? s) => string.IsNullOrWhiteSpace(s) ? null : s.Trim();
}
