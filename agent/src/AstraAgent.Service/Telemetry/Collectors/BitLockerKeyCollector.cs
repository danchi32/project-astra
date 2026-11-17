using System.Management;
using System.Text.RegularExpressions;

namespace AstraAgent.Service.Telemetry.Collectors;

/// <summary>One BitLocker recovery password, as escrowed to SAVIO (the Intune job).</summary>
public sealed record BitLockerRecoveryKey(string Drive, string ProtectorId, string RecoveryPassword);

public interface IBitLockerKeyCollector
{
    /// <summary>The recovery passwords of every drive that BitLocker protects. Empty when none
    /// are protected or nothing can be read. Never logged: these are credentials.</summary>
    IReadOnlyList<BitLockerRecoveryKey> Collect();
}

/// <summary>Reads recovery passwords through Win32_EncryptableVolume, the interface
/// manage-bde itself uses. Runs as LocalSystem, which these methods require.
///
/// Only the numerical-password protector (KeyProtectorType 3) is a recovery password; the TPM,
/// PIN and startup-key protectors are not something an admin can type at the recovery
/// screen, so they are never read.</summary>
public sealed class BitLockerKeyCollector(ILogger<BitLockerKeyCollector> logger) : IBitLockerKeyCollector
{
    private const uint NumericalPasswordProtector = 3;
    private static readonly Regex Drive = new(@"^[A-Z]:$", RegexOptions.Compiled);
    private static readonly Regex Guid = new(@"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", RegexOptions.Compiled);
    private static readonly Regex Recovery = new(@"^\d{6}(-\d{6}){7}$", RegexOptions.Compiled);

    public IReadOnlyList<BitLockerRecoveryKey> Collect()
    {
        var keys = new List<BitLockerRecoveryKey>();
        try
        {
            using var searcher = new ManagementObjectSearcher(
                @"root\CIMV2\Security\MicrosoftVolumeEncryption",
                "SELECT * FROM Win32_EncryptableVolume");
            foreach (ManagementObject volume in searcher.Get())
            {
                // One volume that throws must not cost every other volume its key.
                try
                {
                    var drive = volume["DriveLetter"]?.ToString()?.ToUpperInvariant();
                    if (drive is null || !Drive.IsMatch(drive)) continue;
                    if (!ShouldReadKeys(AsInt(volume["ProtectionStatus"]), AsInt(volume["ConversionStatus"]))) continue;

                    foreach (var id in ProtectorIds(volume))
                    {
                        var normalized = NormalizeProtectorId(id);
                        var password = NumericalPassword(volume, id)?.Trim();
                        if (normalized is null || password is null || !IsRecoveryPassword(password)) continue;
                        keys.Add(new BitLockerRecoveryKey(drive, normalized, password));
                    }
                }
                catch (Exception ex)
                {
                    logger.LogDebug("One BitLocker volume not readable: {Type}", ex.GetType().Name);
                }
            }
        }
        catch (Exception ex)
        {
            // No message text that could carry key material: only the failure type.
            logger.LogDebug("BitLocker recovery keys not readable: {Type}", ex.GetType().Name);
        }
        return keys;
    }

    private static IEnumerable<string> ProtectorIds(ManagementObject volume)
    {
        var args = volume.GetMethodParameters("GetKeyProtectors");
        args["KeyProtectorType"] = NumericalPasswordProtector;
        var result = volume.InvokeMethod("GetKeyProtectors", args, null);
        return result?["VolumeKeyProtectorID"] as string[] ?? [];
    }

    private static string? NumericalPassword(ManagementObject volume, string protectorId)
    {
        var args = volume.GetMethodParameters("GetKeyProtectorNumericalPassword");
        args["VolumeKeyProtectorID"] = protectorId;
        var result = volume.InvokeMethod("GetKeyProtectorNumericalPassword", args, null);
        return result?["NumericalPassword"] as string;
    }

    private static int? AsInt(object? v) => int.TryParse(v?.ToString(), out var n) ? n : null;

    // ── pure helpers (unit-tested) ──────────────────────────────────────────

    /// <summary>Read a volume's keys when it is protected, or when it holds encrypted data even
    /// though protection is suspended (Windows suspends it for updates, and mid-encryption).
    /// A fully decrypted volume (ConversionStatus 0) has no key worth escrowing.</summary>
    internal static bool ShouldReadKeys(int? protectionStatus, int? conversionStatus) =>
        protectionStatus == 1 || (conversionStatus is not null && conversionStatus != 0);

    internal static bool IsRecoveryPassword(string value) => Recovery.IsMatch(value.Trim());

    /// <summary>"{ABC…}" → "abc…", or null when it is not a GUID.</summary>
    internal static string? NormalizeProtectorId(string value)
    {
        var id = value.Trim().Trim('{', '}').ToLowerInvariant();
        return Guid.IsMatch(id) ? id : null;
    }

    /// <summary>The keys not yet escrowed in this run, so a recovery password crosses the
    /// network once per service start, not every hour.</summary>
    internal static IReadOnlyList<BitLockerRecoveryKey> NotYetEscrowed(
        IEnumerable<BitLockerRecoveryKey> keys, IReadOnlySet<string> escrowed) =>
        keys.Where(k => !escrowed.Contains(k.Drive + "|" + k.ProtectorId)).ToList();

    internal static string EscrowKey(BitLockerRecoveryKey k) => k.Drive + "|" + k.ProtectorId;
}
