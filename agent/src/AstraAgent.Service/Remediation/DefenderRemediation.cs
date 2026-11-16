using System.Diagnostics;
using System.Management;
using System.Text.RegularExpressions;

namespace AstraAgent.Service.Remediation;

/// <summary>Turns Defender real-time protection on (2a+ fix action, admin_only).
///
/// Two conditions, both checked here and not left to the portal:
///   1. Defender is the only antivirus registered with Windows Security Center. A third-party AV
///      owns real-time protection, and switching Defender on under it fights that product.
///   2. Afterwards real-time protection is read back as ON.
///
/// Tamper Protection is never changed. If it stops the change, the action reports that and
/// stops, and the device stays as it was. The command is fixed: no parameters from the caller.</summary>
public static class DefenderRemediation
{
    private static readonly Regex DefenderName = new(@"^(windows|microsoft) defender", RegexOptions.IgnoreCase | RegexOptions.Compiled);

    public static (bool Success, string Output) EnableRealtime()
    {
        var registered = AntivirusProducts();
        if (registered is null)
            return (false, "Could not read the antivirus list from Windows Security Center, so SAVIO "
                           + "can't confirm Defender is the only antivirus. Nothing was changed.");
        if (!IsDefenderSole(registered))
            return (false, "Another antivirus is registered on this PC ("
                           + string.Join(", ", registered.Where(n => !DefenderName.IsMatch(n))) + "). "
                           + "Turn on Defender through that product, or leave it as it is. Nothing was changed.");

        if (ReadRealtime() == true)
            return (true, "Defender real-time protection was already on.");

        // WMI first: no PowerShell process, no module search path. PowerShell (by full path) only
        // if WMI refuses, since some builds expose the method differently.
        var (setOk, setOut) = SetRealtimeOnViaWmi();
        if (!setOk)
            (setOk, setOut) = Run(
                Path.Combine(Environment.SystemDirectory, "WindowsPowerShell", "v1.0", "powershell.exe"),
                "-NoProfile", "-NonInteractive", "-Command", "Set-MpPreference -DisableRealtimeMonitoring $false");
        var after = ReadRealtime();
        if (after == true)
            return (true, "Defender real-time protection is now on.");

        return (false, "Defender real-time protection is still off after the change"
                       + (setOk ? "" : " (" + Tail(setOut) + ")")
                       + ". If Tamper Protection is on, change it in Windows Security, or check Group Policy.");
    }

    /// <summary>True only when at least one product is registered and every one of them is
    /// Defender. An empty list is not "Defender only": it means the check could not see anything.</summary>
    internal static bool IsDefenderSole(IReadOnlyList<string> displayNames) =>
        displayNames.Count > 0 && displayNames.All(IsDefenderName);

    internal static bool IsDefenderName(string displayName) => DefenderName.IsMatch(displayName.Trim());

    private static (bool Ok, string Output) SetRealtimeOnViaWmi()
    {
        try
        {
            using var cls = new ManagementClass(@"root\Microsoft\Windows\Defender", "MSFT_MpPreference", null);
            var args = cls.GetMethodParameters("Set");
            args["DisableRealtimeMonitoring"] = false;
            var result = cls.InvokeMethod("Set", args, null);
            var rv = result?["ReturnValue"];
            return (rv is null || Convert.ToInt64(rv) == 0, $"MSFT_MpPreference.Set returned {rv ?? "nothing"}");
        }
        catch (Exception ex)
        {
            return (false, ex.GetType().Name);
        }
    }

    /// <summary>Null when the list cannot be read at all.</summary>
    private static IReadOnlyList<string>? AntivirusProducts()
    {
        try
        {
            using var searcher = new ManagementObjectSearcher(@"root\SecurityCenter2",
                "SELECT displayName FROM AntiVirusProduct");
            return searcher.Get().Cast<ManagementObject>()
                .Select(o => o["displayName"]?.ToString() ?? "")
                .Where(n => n.Length > 0)
                .ToList();
        }
        catch
        {
            return null;
        }
    }

    /// <summary>MSFT_MpComputerStatus.RealTimeProtectionEnabled, or null when Defender can't be read.</summary>
    private static bool? ReadRealtime()
    {
        try
        {
            using var searcher = new ManagementObjectSearcher(@"root\Microsoft\Windows\Defender",
                "SELECT RealTimeProtectionEnabled FROM MSFT_MpComputerStatus");
            foreach (var obj in searcher.Get())
                return obj["RealTimeProtectionEnabled"] is bool b ? b : null;
        }
        catch
        {
            // Defender namespace absent: nothing to read back, so the caller reports it as not on.
        }
        return null;
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
            var stdout = process.StandardOutput.ReadToEndAsync();
            var stderr = process.StandardError.ReadToEndAsync();
            if (!process.WaitForExit(120_000))
            {
                try { process.Kill(entireProcessTree: true); } catch { /* best effort */ }
                return (false, "timed out");
            }
            return (process.ExitCode == 0, stdout.GetAwaiter().GetResult() + "\n" + stderr.GetAwaiter().GetResult());
        }
        catch (Exception ex)
        {
            return (false, ex.Message);
        }
    }
}
