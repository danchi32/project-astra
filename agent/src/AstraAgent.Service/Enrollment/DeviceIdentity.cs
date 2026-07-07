using System.Management;
using System.Runtime.InteropServices;
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
    public DeviceIdentity Collect() => new(
        Environment.MachineName,
        GetMachineGuid(),
        Truncate(RuntimeInformation.OSDescription.Trim(), 100),
        GetBiosSerialNumber());

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
