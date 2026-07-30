using System.Management;
using Microsoft.Win32;

namespace AstraAgent.Service.Enrollment;

public sealed record DeviceIdentity(
    string Hostname,
    string MachineId,
    string OsVersion,
    string? SerialNumber);

public interface IDeviceIdentityProvider
{
    DeviceIdentity Collect();
}

public sealed class WindowsDeviceIdentityProvider(ILogger<WindowsDeviceIdentityProvider> logger)
    : IDeviceIdentityProvider
{
    private const string CurrentVersionKey = @"SOFTWARE\Microsoft\Windows NT\CurrentVersion";

    public DeviceIdentity Collect() => new(
        Environment.MachineName,
        GetMachineGuid(),
        GetOsVersion(),
        GetBiosSerialNumber());

    /// <summary>The OS as a human would name it: "Windows 11 Enterprise 25H2 (build 26200.8893)".
    ///
    /// This used to be RuntimeInformation.OSDescription, which returns "Microsoft Windows
    /// 10.0.26200" — the KERNEL version, which Microsoft deliberately left at 10.0 for
    /// Windows 11. So every Windows 11 device in the fleet reported itself as "Windows 10".
    /// Not merely vague: with Windows 10 out of support, "which machines are still on 10" is
    /// a question the portal could not answer, and would have answered wrongly.
    ///
    /// Win32_OperatingSystem.Caption is the one source that names 11 as 11. The registry's
    /// ProductName is NOT — it still reads "Windows 10 Enterprise" on Windows 11, so it is
    /// used here only for DisplayVersion ("25H2"), which it does report correctly.</summary>
    public string GetOsVersion()
    {
        var build = Environment.OSVersion.Version.Build;
        var name = GetOsCaption();

        if (string.IsNullOrWhiteSpace(name))
        {
            // WMI unavailable (service disabled, broken repository). The build number alone
            // still separates 11 from 10 — that split is what the fleet is judged on.
            name = build >= 22000 ? "Windows 11" : "Windows 10";
            logger.LogWarning("OS caption unreadable; naming the OS from build {Build}", build);
        }

        var display = GetDisplayVersion();
        var ubr = GetUpdateBuildRevision();
        var buildText = ubr is null ? $"build {build}" : $"build {build}.{ubr}";

        var full = string.IsNullOrWhiteSpace(display)
            ? $"{name} ({buildText})"
            : $"{name} {display} ({buildText})";
        return Truncate(full, 100);
    }

    private string? GetOsCaption()
    {
        try
        {
            using var searcher = new ManagementObjectSearcher("SELECT Caption FROM Win32_OperatingSystem");
            foreach (var obj in searcher.Get())
            {
                var caption = obj["Caption"]?.ToString()?.Trim();
                if (string.IsNullOrWhiteSpace(caption)) continue;
                // "Microsoft Windows 11 Enterprise" -> "Windows 11 Enterprise". The vendor
                // prefix is the same on every row and costs characters we need for the build.
                return caption.StartsWith("Microsoft ", StringComparison.OrdinalIgnoreCase)
                    ? caption["Microsoft ".Length..]
                    : caption;
            }
        }
        catch (Exception ex)
        {
            logger.LogWarning(ex, "Could not read OS caption from WMI");
        }
        return null;
    }

    private static string? GetDisplayVersion()
    {
        // "25H2". Absent before Windows 10 2004, where ReleaseId ("1909") was the equivalent.
        using var key = Registry.LocalMachine.OpenSubKey(CurrentVersionKey);
        var display = key?.GetValue("DisplayVersion") as string;
        if (!string.IsNullOrWhiteSpace(display)) return display;
        return key?.GetValue("ReleaseId") as string;
    }

    private static int? GetUpdateBuildRevision()
    {
        // The patch level within the build (the ".8893"), which is what actually moves when
        // a cumulative update installs.
        using var key = Registry.LocalMachine.OpenSubKey(CurrentVersionKey);
        return key?.GetValue("UBR") as int?;
    }

    private string GetMachineGuid()
    {
        using var key = Registry.LocalMachine.OpenSubKey(@"SOFTWARE\Microsoft\Cryptography");
        var guid = key?.GetValue("MachineGuid") as string;
        if (!string.IsNullOrWhiteSpace(guid))
            return guid;
        logger.LogWarning("MachineGuid not readable; falling back to machine name");
        return Environment.MachineName;
    }

    private string? GetBiosSerialNumber()
    {
        try
        {
            using var searcher = new ManagementObjectSearcher("SELECT SerialNumber FROM Win32_BIOS");
            foreach (var obj in searcher.Get())
            {
                var serial = obj["SerialNumber"]?.ToString()?.Trim();
                if (!string.IsNullOrWhiteSpace(serial))
                    return Truncate(serial, 100);
            }
        }
        catch (Exception ex)
        {
            logger.LogWarning(ex, "Could not read BIOS serial number");
        }
        return null;
    }

    private static string Truncate(string value, int max) =>
        value.Length <= max ? value : value[..max];
}
