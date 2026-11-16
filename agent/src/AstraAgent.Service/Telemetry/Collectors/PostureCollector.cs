using System.Management;
using System.Text.RegularExpressions;

namespace AstraAgent.Service.Telemetry.Collectors;

/// <summary>The security posture facts behind the Security Score (2a). Each field is null when
/// it could not be read — null is "unknown", never "off". The backend decides pass or fail.</summary>
public sealed record PostureReport(
    bool? DefenderRealtime,
    int? DefenderSignatureAgeDays,
    bool? FirewallDomain,
    bool? FirewallPrivate,
    bool? FirewallPublic,
    bool? BitLockerOsDrive,
    // Another antivirus is registered with Security Center. Defender's real-time protection is
    // off by design beside it, which must not read as an unprotected PC. Null = not readable.
    bool? ThirdPartyAntivirus = null);

public interface IPostureCollector
{
    /// <summary>Null when nothing at all could be read this cycle. The worker then sends no
    /// posture block, so the backend keeps the last known state instead of marking everything
    /// unknown because of one bad WMI call.</summary>
    PostureReport? Collect();
}

/// <summary>Reads Defender, firewall and BitLocker state from the WMI classes Windows itself uses
/// (the same ones the Security and Windows Defender consoles read). Every read is independent,
/// so one unavailable class does not hide the others.
///
/// Runs every push, not with the hourly inventory: a Defender turned off must show within one
/// cycle, and the reads are a few milliseconds each.</summary>
public sealed class PostureCollector(ILogger<PostureCollector> logger) : IPostureCollector
{
    private static readonly Regex DriveLetter = new(@"^[A-Za-z]:$", RegexOptions.Compiled);

    public PostureReport? Collect()
    {
        var (realtime, sigAge) = ReadDefender();
        var (domain, priv, pub) = ReadFirewall();
        var bitlocker = ReadBitLocker();
        var thirdParty = ReadThirdPartyAntivirus();

        var report = new PostureReport(realtime, sigAge, domain, priv, pub, bitlocker, thirdParty);
        var anyKnown = realtime is not null || sigAge is not null || domain is not null
                       || priv is not null || pub is not null || bitlocker is not null;
        return anyKnown ? report : null;
    }

    private (bool? realtime, int? sigAge) ReadDefender()
    {
        try
        {
            using var searcher = new ManagementObjectSearcher(
                @"root\Microsoft\Windows\Defender",
                "SELECT RealTimeProtectionEnabled, AntivirusSignatureAge FROM MSFT_MpComputerStatus");
            foreach (var obj in searcher.Get())
                return (ParseBool(obj["RealTimeProtectionEnabled"]), ParseAgeDays(obj["AntivirusSignatureAge"]));
        }
        catch (Exception ex)
        {
            // Defender absent (removed, or a third-party AV that owns the namespace) is a real
            // answer for the backend too: unknown, not a pass.
            logger.LogDebug(ex, "Defender status not readable");
        }
        return (null, null);
    }

    private (bool? domain, bool? priv, bool? pub) ReadFirewall()
    {
        // The effective state after Group Policy, not the local settings (security review, 2a+).
        try { return FirewallProfiles.ReadActive(); }
        catch (Exception ex)
        {
            logger.LogDebug(ex, "Firewall profiles not readable");
            return (null, null, null);
        }
    }

    private bool? ReadThirdPartyAntivirus()
    {
        try
        {
            using var searcher = new ManagementObjectSearcher(@"root\SecurityCenter2",
                "SELECT displayName FROM AntiVirusProduct");
            var names = searcher.Get().Cast<ManagementObject>()
                .Select(o => o["displayName"]?.ToString() ?? "").Where(n => n.Length > 0).ToList();
            return HasThirdPartyAntivirus(names);
        }
        catch (Exception ex)
        {
            logger.LogDebug(ex, "Antivirus list not readable");
            return null;
        }
    }

    /// <summary>True when any registered antivirus is not Defender. An empty list is false:
    /// nothing else registered.</summary>
    internal static bool HasThirdPartyAntivirus(IReadOnlyList<string> displayNames) =>
        displayNames.Any(n => !Remediation.DefenderRemediation.IsDefenderName(n));

    private bool? ReadBitLocker()
    {
        var drive = SystemDriveLetter(Environment.SystemDirectory);
        if (drive is null) return null;
        try
        {
            // The drive letter is validated above, so the query text is fixed apart from "X:".
            using var searcher = new ManagementObjectSearcher(
                @"root\CIMV2\Security\MicrosoftVolumeEncryption",
                $"SELECT ProtectionStatus FROM Win32_EncryptableVolume WHERE DriveLetter = '{drive}'");
            foreach (var obj in searcher.Get())
                return ParseProtectionStatus(obj["ProtectionStatus"]);
        }
        catch (Exception ex)
        {
            // No TPM, or BitLocker never set up on this machine: no volume object at all.
            logger.LogDebug(ex, "BitLocker state not readable");
        }
        return null;
    }

    // ── parsing (pure, unit-tested) ─────────────────────────────────────────

    /// <summary>A WMI boolean, which some classes send as a bool and some as 0 / 1.</summary>
    internal static bool? ParseBool(object? v) => v switch
    {
        bool b => b,
        null => null,
        _ => int.TryParse(v.ToString(), out var n) switch
        {
            true when n == 1 => true,
            true when n == 0 => false,
            _ => null,
        },
    };

    /// <summary>MSFT_NetFirewallProfile.Enabled is a GpoBoolean: 0 False, 1 True, 2 NotConfigured.
    /// NotConfigured says nothing about the state, so it is unknown rather than off.</summary>
    internal static bool? ParseGpoBool(object? v) => ParseBool(v);

    /// <summary>Signature age in whole days, or null when absent or implausible. The upper bound
    /// keeps a corrupt value from becoming a number the backend will refuse to accept.</summary>
    internal static int? ParseAgeDays(object? v)
    {
        if (v is null || !long.TryParse(v.ToString(), out var n)) return null;
        return n is >= 0 and <= 3650 ? (int)n : null;
    }

    /// <summary>Win32_EncryptableVolume.ProtectionStatus: 0 Off, 1 On, 2 Unknown.</summary>
    internal static bool? ParseProtectionStatus(object? v) => v is null
        ? null
        : int.TryParse(v.ToString(), out var n) switch
        {
            true when n == 1 => true,
            true when n == 0 => false,
            _ => null,
        };

    /// <summary>"C:" for a system directory on C:\. Anything that is not a plain drive letter gives
    /// null, so the value can never carry WQL syntax into the query.</summary>
    internal static string? SystemDriveLetter(string systemDirectory)
    {
        var root = Path.GetPathRoot(systemDirectory)?.TrimEnd('\\');
        return root is not null && DriveLetter.IsMatch(root) ? root.ToUpperInvariant() : null;
    }
}
