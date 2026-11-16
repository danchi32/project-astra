using System.Diagnostics;
using System.Text.RegularExpressions;

namespace AstraAgent.Service.Remediation;

/// <summary>Turns Windows Firewall on for all three profiles (domain, private, public).
///
/// No parameters: the command is fixed by the action id, so nothing a caller sends can point it
/// at another setting. Runs as LocalSystem, the same as the other machine-wide fixes.
///
/// It checks the result rather than trusting the exit code: a firewall held by Group Policy can
/// refuse the change while netsh still reports success, and the Security Score must not claim a
/// recovery that did not happen.</summary>
public static class FirewallRemediation
{
    private static readonly Regex StateLine = new(@"^\s*State\s+(ON|OFF)\s*$", RegexOptions.Multiline | RegexOptions.IgnoreCase);

    public static (bool Success, string Output) EnableAllProfiles()
    {
        var (setOk, setOut) = Run("netsh.exe", "advfirewall", "set", "allprofiles", "state", "on");
        if (!setOk)
            return (false, "Windows Firewall did not accept the change. " + Tail(setOut)
                           + " If a Group Policy controls the firewall, change it there.");

        var (showOk, showOut) = Run("netsh.exe", "advfirewall", "show", "allprofiles", "state");
        if (!showOk)
            return (false, "The change was sent, but the firewall state could not be read back. "
                           + "Check the device before counting this as fixed.");

        return AllOn(showOut)
            ? (true, "Windows Firewall is on for the domain, private and public profiles.")
            : (false, "Windows Firewall is still off for at least one profile after the change. "
                      + "A Group Policy or a third-party firewall is probably controlling it.");
    }

    /// <summary>True only when every profile reports ON. Three profiles are expected; a
    /// missing or unreadable one counts as not on.</summary>
    internal static bool AllOn(string showOutput)
    {
        var states = StateLine.Matches(showOutput)
            .Select(m => m.Groups[1].Value.ToUpperInvariant())
            .ToList();
        return states.Count == 3 && states.All(s => s == "ON");
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
                FileName = exe,
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
