using System.Text.RegularExpressions;

namespace AstraAgent.Service.Guard;

/// <summary>
/// Phase 3 · D10 / D1 / D2: the browser lock-down an organization asks for, independent of the
/// browser. <see cref="BrowserPolicyMap"/> turns it into each browser's own policy names, and
/// <see cref="BrowserPolicyWriter"/> applies them.
///
/// Every field is "off" by default: an empty policy changes nothing. Values are validated
/// here, before anything reaches the registry or a policy file. The policy comes from the
/// backend, and a bad value there must not become a broken or hostile browser setting.
/// </summary>
public sealed record BrowserPolicy
{
    public bool IncognitoOff { get; init; }
    /// <summary>Chrome/Edge: no "Load unpacked" on the extensions page.</summary>
    public bool ExtensionDeveloperModeOff { get; init; }
    /// <summary>All developer tools. Broader than the above, so a separate choice. On
    /// Firefox it is the only way to stop temporary add-ons from about:debugging.</summary>
    public bool DevToolsOff { get; init; }
    /// <summary>No new browser profiles or guest windows, which would run without the
    /// extension's per-profile state.</summary>
    public bool NewProfilesOff { get; init; }
    /// <summary>Host names (and their subdomains) to block, or to allow despite a block.</summary>
    public IReadOnlyList<string> BlockedSites { get; init; } = Array.Empty<string>();
    public IReadOnlyList<string> AllowedSites { get; init; } = Array.Empty<string>();
    /// <summary>D2: Google sign-in only for these Workspace domains (X-GoogApps-Allowed-Domains).</summary>
    public IReadOnlyList<string> GoogleAllowedDomains { get; init; } = Array.Empty<string>();
    /// <summary>The SAVIO extension's store IDs, set once it is published. Empty = not forced.</summary>
    public string? ChromeExtensionId { get; init; }
    public string? EdgeExtensionId { get; init; }
    public string? FirefoxExtensionId { get; init; }
    public string? FirefoxExtensionUrl { get; init; }

    /// <summary>D3: the extension's own settings, handed to it as managed policy wherever it is
    /// forced in. log = record only; warn = ask first; block = refuse.</summary>
    public string GuardMode { get; init; } = "log";
    /// <summary>Hosts the extension watches (subdomains included). Empty = every site.</summary>
    public IReadOnlyList<string> GuardWatchedSites { get; init; } = Array.Empty<string>();
    /// <summary>Finding kinds recorded but never acted on. E-mail addresses by default: they are everywhere.</summary>
    public IReadOnlyList<string> GuardIgnoreKinds { get; init; } = ["Email"];
    public IReadOnlyList<string> GuardKeywords { get; init; } = Array.Empty<string>();

    public const int MaxSites = 500;
    public const int MaxKeywords = 200;
    static readonly string[] Modes = ["log", "warn", "block"];
    /// <summary>AstraAgent.Guard's Finding names, which the extension sees in the host's counts.</summary>
    static readonly string[] Kinds = ["Aadhaar", "Pan", "Gstin", "PaymentCard", "IndianMobile", "Email", "BankAccount"];
    static readonly Regex Host = new(@"^(?=.{1,253}$)(?!-)[a-z0-9-]{1,63}(?<!-)(\.(?!-)[a-z0-9-]{1,63}(?<!-))+$", RegexOptions.CultureInvariant);
    static readonly Regex ChromiumId = new("^[a-p]{32}$", RegexOptions.CultureInvariant);
    static readonly Regex FirefoxId = new(@"^(\{[0-9a-fA-F-]{36}\}|[A-Za-z0-9._-]{1,80}@[A-Za-z0-9.-]{1,80})$", RegexOptions.CultureInvariant);

    /// <summary>Problems that make this policy unsafe to apply. Empty = valid.</summary>
    public IReadOnlyList<string> Validate()
    {
        var problems = new List<string>();
        foreach (var (name, list) in new[] { ("blocked site", BlockedSites), ("allowed site", AllowedSites),
                                             ("Google domain", GoogleAllowedDomains) })
        {
            if (list.Count > MaxSites) problems.Add($"too many {name}s (max {MaxSites})");
            problems.AddRange(list.Where(h => !Host.IsMatch(h ?? "")).Select(h => $"{name} '{Trim(h)}' is not a host name"));
        }
        if (ChromeExtensionId is { } c && !ChromiumId.IsMatch(c)) problems.Add("Chrome extension ID is malformed");
        if (EdgeExtensionId is { } e && !ChromiumId.IsMatch(e)) problems.Add("Edge extension ID is malformed");
        if (FirefoxExtensionId is { } f && !FirefoxId.IsMatch(f)) problems.Add("Firefox extension ID is malformed");
        if (FirefoxExtensionId is not null != FirefoxExtensionUrl is not null)
            problems.Add("Firefox extension needs both an ID and an install URL");
        if (FirefoxExtensionUrl is { } u &&
            !(Uri.TryCreate(u, UriKind.Absolute, out var uri) && uri.Scheme == Uri.UriSchemeHttps && u.Length <= 500))
            problems.Add("Firefox extension URL must be https");
        if (!Modes.Contains(GuardMode)) problems.Add($"guard mode '{Trim(GuardMode)}' is not log, warn or block");
        if (GuardWatchedSites.Count > MaxSites) problems.Add($"too many watched sites (max {MaxSites})");
        problems.AddRange(GuardWatchedSites.Where(h => !Host.IsMatch(h ?? "")).Select(h => $"watched site '{Trim(h)}' is not a host name"));
        problems.AddRange(GuardIgnoreKinds.Where(k => !Kinds.Contains(k)).Select(k => $"'{Trim(k)}' is not a kind of finding"));
        if (GuardKeywords.Count > MaxKeywords) problems.Add($"too many keywords (max {MaxKeywords})");
        if (GuardKeywords.Any(k => string.IsNullOrWhiteSpace(k) || k.Length > 100)) problems.Add("keywords must be 1–100 characters");
        return problems;
    }

    static string Trim(string? s) => (s ?? "").Length > 60 ? s![..60] + "…" : s ?? "";
}

public enum Browser { Chrome, Edge, Firefox }

/// <summary>
/// A browser's own name for each setting. Chromium policies are registry values, or list
/// subkeys with values "1", "2", …. Firefox policies are keys in policies.json. Each entry is
/// one *policy*: the unit SAVIO owns, writes, checks, and removes as a whole.
/// </summary>
public static class BrowserPolicyMap
{
    const string ChromeStore = "https://clients2.google.com/service/update2/crx";
    const string EdgeStore = "https://edge.microsoft.com/extensionwebstorebase/v1/crx";

    /// <summary>Chromium (Chrome, Edge): DWORD values (int), strings, or lists (string[]).</summary>
    public static IReadOnlyDictionary<string, object> Chromium(BrowserPolicy p, Browser b)
    {
        if (b == Browser.Firefox) throw new ArgumentException("not a Chromium browser", nameof(b));
        var edge = b == Browser.Edge;
        var v = new Dictionary<string, object>(StringComparer.OrdinalIgnoreCase);
        if (p.IncognitoOff) v[edge ? "InPrivateModeAvailability" : "IncognitoModeAvailability"] = 1;
        if (p.ExtensionDeveloperModeOff) v["ExtensionDeveloperModeSettings"] = 1;
        if (p.DevToolsOff) v["DeveloperToolsAvailability"] = 2;
        if (p.NewProfilesOff)
        {
            v[edge ? "BrowserAddProfileEnabled" : "BrowserAddPersonEnabled"] = 0;
            v["BrowserGuestModeEnabled"] = 0;
        }
        if (p.BlockedSites.Count > 0) v["URLBlocklist"] = p.BlockedSites.ToArray();
        if (p.AllowedSites.Count > 0) v["URLAllowlist"] = p.AllowedSites.ToArray();
        if (p.GoogleAllowedDomains.Count > 0) v["AllowedDomainsForApps"] = string.Join(",", p.GoogleAllowedDomains);
        var id = edge ? p.EdgeExtensionId : p.ChromeExtensionId;
        if (id is not null)
        {
            v["ExtensionInstallForcelist"] = new[] { $"{id};{(edge ? EdgeStore : ChromeStore)}" };
            v[$@"3rdparty\extensions\{id}\policy"] = GuardSettings(p);
        }
        return v;
    }

    /// <summary>D3: the extension's managed settings, named as in extension/managed_schema.json.</summary>
    static Dictionary<string, object> GuardSettings(BrowserPolicy p) => new()
    {
        ["mode"] = p.GuardMode,
        ["watchedSites"] = p.GuardWatchedSites.ToArray(),
        ["ignoreKinds"] = p.GuardIgnoreKinds.ToArray(),
        ["keywords"] = p.GuardKeywords.ToArray(),
    };

    /// <summary>Firefox: top-level keys of the "policies" object in policies.json.</summary>
    public static IReadOnlyDictionary<string, object> Firefox(BrowserPolicy p)
    {
        var v = new Dictionary<string, object>(StringComparer.Ordinal);
        if (p.IncognitoOff) v["DisablePrivateBrowsing"] = true;
        if (p.DevToolsOff) v["DisableDeveloperTools"] = true;
        if (p.BlockedSites.Count > 0 || p.AllowedSites.Count > 0)
            v["WebsiteFilter"] = new Dictionary<string, object>
            {
                // Firefox takes match patterns; a host covers itself and its subdomains, as in Chrome.
                ["Block"] = p.BlockedSites.SelectMany(Patterns).ToArray(),
                ["Exceptions"] = p.AllowedSites.SelectMany(Patterns).ToArray(),
            };
        if (p.GoogleAllowedDomains.Count > 0) v["AllowedDomainsForApps"] = string.Join(",", p.GoogleAllowedDomains);
        if (p.FirefoxExtensionId is not null && p.FirefoxExtensionUrl is not null)
        {
            v["ExtensionSettings"] = new Dictionary<string, object>
            {
                [p.FirefoxExtensionId] = new Dictionary<string, object>
                {
                    ["installation_mode"] = "force_installed",
                    ["install_url"] = p.FirefoxExtensionUrl,
                },
            };
            v[$@"3rdparty\Extensions\{p.FirefoxExtensionId}"] = GuardSettings(p);
        }
        return v;
    }

    static IEnumerable<string> Patterns(string host) => new[] { $"*://{host}/*", $"*://*.{host}/*" };
}
