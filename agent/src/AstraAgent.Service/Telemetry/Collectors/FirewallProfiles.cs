using System.Management;

namespace AstraAgent.Service.Telemetry.Collectors;

/// <summary>The EFFECTIVE Windows Firewall state per profile, after Group Policy.
///
/// MSFT_NetFirewallProfile read with no policy store returns the local settings, which is what
/// `netsh advfirewall show` prints too. A firewall turned off by a domain policy then reads ON
/// locally while it is off in practice. Reading the ActiveStore gives the state Windows actually
/// enforces. It is also language-neutral, unlike netsh's translated text ("Status EIN").</summary>
public static class FirewallProfiles
{
    /// <summary>(domain, private, public). A null is a profile that was not reported. Throws when
    /// the class cannot be read at all; callers decide what that means.</summary>
    public static (bool? Domain, bool? Private, bool? Public) ReadActive()
    {
        bool? domain = null, priv = null, pub = null;
        var options = new System.Management.EnumerationOptions { Context = new ManagementNamedValueCollection() };
        options.Context.Add("PolicyStore", "ActiveStore");
        using var searcher = new ManagementObjectSearcher(
            new ManagementScope(@"root\StandardCimv2"),
            new ObjectQuery("SELECT Name, Enabled FROM MSFT_NetFirewallProfile"),
            options);
        foreach (var obj in searcher.Get())
        {
            var state = PostureCollector.ParseGpoBool(obj["Enabled"]);
            switch (obj["Name"]?.ToString())
            {
                case "Domain": domain = state; break;
                case "Private": priv = state; break;
                case "Public": pub = state; break;
            }
        }
        return (domain, priv, pub);
    }
}
