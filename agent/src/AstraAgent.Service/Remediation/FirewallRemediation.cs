using System.Diagnostics;
using System.Management;
using System.Text.RegularExpressions;
using AstraAgent.Service.Telemetry.Collectors;

namespace AstraAgent.Service.Remediation;

/// <summary>Turns Windows Firewall on for all three profiles (domain, private, public).
///
/// No parameters: the command is fixed by the action id, so nothing a caller sends can point it
/// at another setting. Runs as LocalSystem, the same as the other machine-wide fixes.
///
/// Two guards (security review, 2a+):
///   1. It refuses when another firewall is registered with Windows Security Center. Windows
///      Firewall is off by design beside it, and turning it on across a fleet next to another
///      product can block line-of-business traffic.
///   2. Success is read back from the EFFECTIVE state (FirewallProfiles.ReadActive), not netsh's
///      exit code or its text: a Group Policy can keep the firewall off while netsh reports
///      success, and netsh's output is translated on non-English Windows.</summary>
public static class FirewallRemediation
{
    private static readonly Regex WindowsFirewall =
        new(@"^(windows|microsoft)( defender)? firewall", RegexOptions.IgnoreCase | RegexOptions.Compiled);

    public static (bool Success, string Output) EnableAllProfiles()
    {
        var registered = FirewallProducts();
        if (registered is null)
            return (false, "Could not read the firewall list from Windows Security Center, so SAVIO "
                           + "can't confirm no other firewall is in charge. Nothing was changed.");
        var others = OtherFirewalls(registered);
        if (others.Count > 0)
            return (false, "Another firewall is registered on this PC (" + string.Join(", ", others) + "). "
                           + "Windows Firewall is off beside it by design. Nothing was changed.");

        var (setOk, setOut) = Run("netsh.exe", "advfirewall", "set", "allprofiles", "state", "on");

        (bool? Domain, bool? Private, bool? Public) state;
        try { state = FirewallProfiles.ReadActive(); }
        catch
        {
            return (false, "The change was sent, but the effective firewall state could not be read back. "
                           + "Check the device before counting this as fixed.");
        }

        if (AllOn(state))
            return (true, "Windows Firewall is on for the domain, private and public profiles.");
        return (false, "Windows Firewall is still off for at least one profile after the change"
                       + (setOk ? "" : " (" + Tail(setOut) + ")")
                       + ". A Group Policy is probably keeping it off; change it there.");
    }

    /// <summary>True only when all three profiles are known and on.</summary>
    internal static bool AllOn((bool? Domain, bool? Private, bool? Public) s) =>
        s.Domain == true && s.Private == true && s.Public == true;

    /// <summary>Registered firewall products other than Windows Firewall itself.</summary>
    internal static IReadOnlyList<string> OtherFirewalls(IEnumerable<string> displayNames) =>
        displayNames.Select(n => n.Trim()).Where(n => n.Length > 0 && !WindowsFirewall.IsMatch(n)).ToList();

    /// <summary>Null when Security Center cannot be read (Server editions have none).</summary>
    private static IReadOnlyList<string>? FirewallProducts()
    {
        try
        {
            using var searcher = new ManagementObjectSearcher(@"root\SecurityCenter2",
                "SELECT displayName FROM FirewallProduct");
            return searcher.Get().Cast<ManagementObject>()
                .Select(o => o["displayName"]?.ToString() ?? "")
                .ToList();
        }
        catch
        {
            return null;
        }
    }

    private static string Tail(string output)
    {
        var lines = output.Split('\n').Select(l => l.Trim()).Where(l => l.Length > 0).TakeLast(2);
        return string.Join(" ", lines);
    }

    private static (bool Ok, string Output) Run(string exe, params string[] args)
    {
        try
        {
            var psi = new ProcessStartInfo
            {
                FileName = Path.Combine(Environment.SystemDirectory, exe),
                UseShellExecute = false,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                CreateNoWindow = true,
            };
            foreach (var a in args) psi.ArgumentList.Add(a);

            using var process = Process.Start(psi);
            if (process is null) return (false, $"could not start {exe}");

            // Both pipes drained concurrently, so a full stderr buffer cannot stall the child.
            var stdout = process.StandardOutput.ReadToEndAsync();
            var stderr = process.StandardError.ReadToEndAsync();
            if (!process.WaitForExit(60_000))
            {
                try { process.Kill(entireProcessTree: true); } catch { /* best effort */ }
                return (false, "timed out");
            }
            var output = stdout.GetAwaiter().GetResult() + "\n" + stderr.GetAwaiter().GetResult();
            return (process.ExitCode == 0, output);
        }
        catch (Exception ex)
        {
            return (false, ex.Message);
        }
    }
}
