using System.Management;

namespace AstraAgent.Service.Telemetry.Collectors;

/// <summary>One Windows or Office product that holds a product key, as the Software Protection
/// Platform reports it. <paramref name="LicenseStatus"/> is SPP's own code (0 unlicensed,
/// 1 licensed, 2–6 grace / notification states). <paramref name="KmsHost"/> is the KMS server
/// the product is set to activate against, when it activates through KMS at all.
///
/// The agent reports facts only. Deciding what looks like a cracked activation (a KMS host on
/// the loopback address, a known public piracy KMS server, an activator in the app list) is the
/// backend's job, so the signature list can change without shipping an agent.</summary>
public sealed record LicensingProduct(
    string Kind,
    string Name,
    string? Description,
    int LicenseStatus,
    string? Channel,
    string? KmsHost);

public interface ILicensingCollector
{
    /// <summary>Null when SPP could not be read at all — the backend then keeps what it had,
    /// rather than concluding the machine has no licence.</summary>
    IReadOnlyList<LicensingProduct>? GetProducts();
}

public sealed class LicensingCollector(ILogger<LicensingCollector> logger) : ILicensingCollector
{
    // SPP application ids. Office registers here for MSI and volume installs; Microsoft 365
    // Click-to-Run subscriptions use a different licensing stack and simply don't appear,
    // which the backend reports as "unknown", never as a pass or a fail.
    internal const string WindowsAppId = "55c92734-d682-4d71-983e-d6ec3f16059f";
    internal const string OfficeAppId = "0ff1ce15-a989-479d-af46-f275c6370663";

    public IReadOnlyList<LicensingProduct>? GetProducts()
    {
        try
        {
            // PartialProductKey filters to the products that actually hold a key; without it
            // the class lists every SKU Windows *could* be, dozens of them, all unlicensed.
            using var searcher = new ManagementObjectSearcher(
                "SELECT ApplicationID, Name, Description, LicenseStatus, ProductKeyChannel, " +
                "KeyManagementServiceMachine, DiscoveredKeyManagementServiceMachineName " +
                "FROM SoftwareLicensingProduct WHERE PartialProductKey IS NOT NULL");

            var result = new List<LicensingProduct>();
            foreach (var obj in searcher.Get())
            {
                var kind = KindOf(obj["ApplicationID"]?.ToString());
                if (kind is null) continue;

                var name = Clean(obj["Name"]?.ToString(), 200);
                if (name is null) continue;

                result.Add(new LicensingProduct(
                    kind,
                    name,
                    Clean(obj["Description"]?.ToString(), 300),
                    obj["LicenseStatus"] is { } status && int.TryParse(status.ToString(), out var s) ? s : -1,
                    Clean(obj["ProductKeyChannel"]?.ToString(), 50),
                    // An explicitly configured host wins over the one DNS discovery found —
                    // that is the order SPP itself uses, and activators set the explicit one.
                    Clean(obj["KeyManagementServiceMachine"]?.ToString(), 255)
                        ?? Clean(obj["DiscoveredKeyManagementServiceMachineName"]?.ToString(), 255)));
            }
            return result;
        }
        catch (Exception ex)
        {
            logger.LogWarning(ex, "Could not read SoftwareLicensingProduct");
            return null;
        }
    }

    internal static string? KindOf(string? applicationId) => applicationId?.Trim().ToLowerInvariant() switch
    {
        WindowsAppId => "windows",
        OfficeAppId => "office",
        _ => null,
    };

    private static string? Clean(string? value, int max)
    {
        var v = value?.Trim();
        return string.IsNullOrEmpty(v) ? null : v[..Math.Min(v.Length, max)];
    }
}
