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
    /// <summary>"store" (force-installed from the store) or "manual" (installed by hand, for a
    /// pilot or a test). Manual writes no force-install entry: a browser refuses a hand-installed
    /// copy of a force-listed ID. Settings and the native host are set up the same way.</summary>
    public string ExtensionInstall { get; init; } = "store";
    public bool ManualInstall => ExtensionInstall == "manual";

    /// <summary>D3: the extension's own settings, handed to it as managed policy wherever it is
    /// forced in. log = record only; warn = ask first; block = refuse.</summary>
    public string GuardMode { get; init; } = "log";
    /// <summary>Hosts the extension watches (subdomains included). Empty = every site.</summary>
    public IReadOnlyList<string> GuardWatchedSites { get; init; } = Array.Empty<string>();
    /// <summary>Finding kinds recorded but never acted on. E-mail addresses by default: they are everywhere.</summary>
    public IReadOnlyList<string> GuardIgnoreKinds { get; init; } = ["Email"];
    public IReadOnlyList<string> GuardKeywords { get; init; } = Array.Empty<string>();
    /// <summary>D5: once a week, map where sensitive files are on this PC (folder counts only).</summary>
    public bool DiscoveryEnabled { get; init; }
    /// <summary>Read the text inside PDFs: uploads (the extension's <c>readPdf</c>) and the weekly
    /// map. Off: a PDF is "could not check". Word and Excel are read either way.</summary>
    public bool ReadPdfs { get; init; }

    /// <summary>D2 beyond Google: sign-in only to the org's own accounts. Each service enforces it
    /// when its header arrives; the extension adds the header, so these go to it as settings.</summary>
    public string? MicrosoftTenantId { get; init; }
    public string? MicrosoftPolicyId { get; init; }
    /// <summary>The same Microsoft IDs in Windows' own tenant restrictions (v2), so Office apps
    /// (Outlook, Teams, Word…) and Edge on the PC enforce them too, not only the extension.</summary>
    public bool MicrosoftOnWindows { get; init; }
    public IReadOnlyList<string> ClaudeOrgIds { get; init; } = Array.Empty<string>();
    public IReadOnlyList<string> ChatGptWorkspaceIds { get; init; } = Array.Empty<string>();
    public string? SlackRequesterId { get; init; }
    public IReadOnlyList<string> SlackAllowedIds { get; init; } = Array.Empty<string>();
    public const int MaxAccountIds = 50;

    /// <summary>Security review 3b M2: company accounts are enforced by SAVIO's extension, so a
    /// private window (no extension) or another extension that edits request headers gets round
    /// them. With any of them set, a browser that runs SAVIO's extension also has private windows
    /// and guest mode off and every other extension blocked, except these: Chrome / Edge IDs (32
    /// letters a–p) apply to Chrome and Edge, Firefox IDs (name@domain or {GUID}) to Firefox.</summary>
    public IReadOnlyList<string> ExtensionAllowlist { get; init; } = Array.Empty<string>();
    public const int MaxAllowedExtensions = 50;

    /// <summary>A company-accounts rule SAVIO's extension enforces is set.</summary>
    public bool CompanyAccountsLocked =>
        MicrosoftTenantId is not null || ClaudeOrgIds.Count > 0 || ChatGptWorkspaceIds.Count > 0 || SlackRequesterId is not null;

    /// <summary>C3: USB drives and phones. off (SAVIO leaves them alone) · read_only · encrypted_only
    /// (writing only to BitLocker To Go drives) · on_request (read-only, except during a write
    /// window IT opens for this PC) · block (no access at all).</summary>
    public string UsbMode { get; init; } = "off";
    /// <summary>C3: the end of a write window IT opened for this PC, in on_request mode. Not from
    /// the policy: the worker sets it, and the PC enforces the end by itself, online or not.</summary>
    public DateTime? UsbWriteUntil { get; init; }
    /// <summary>C3b: record what is copied onto USB drives, in counts (<see cref="UsbCopyWatcher"/>).
    /// Not a Windows setting: the writer ignores it, except to keep the scanner off the network.</summary>
    public bool UsbObserve { get; init; }
    static readonly string[] UsbModes = ["off", "read_only", "encrypted_only", "on_request", "block", "company_drives"];
    /// <summary>C3b: in company_drives mode, the USB drives that may be used (Windows device
    /// instance IDs, as the PCs reported them). Every other USB drive is not installed.</summary>
    public IReadOnlyList<string> UsbApprovedDrives { get; init; } = Array.Empty<string>();
    public const int MaxApprovedDrives = 100;
    // A drive's USB interface (3b), or its disk as approved before (translated on the PC).
    static readonly Regex DriveId = new(@"^(USB\\VID_[0-9A-Fa-f]{4}&PID_[0-9A-Fa-f]{4}|USBSTOR\\[A-Za-z0-9&_.\-]{1,200})\\[A-Za-z0-9&_.\-]{1,100}$",
                                        RegexOptions.CultureInvariant);

    /// <summary>Close <see cref="OtherBrowsers"/> as they start (<see cref="OtherBrowserBlocker"/>).
    /// Not a browser setting: the writer ignores it.</summary>
    public bool BlockOtherBrowsers { get; init; }

    public const int MaxSites = 500;
    public const int MaxKeywords = 200;
    static readonly string[] Modes = ["log", "warn", "justify", "redact", "approve", "block"];
    /// <summary>AstraAgent.Guard's Finding names, which the extension sees in the host's counts.</summary>
    static readonly string[] Kinds = ["Aadhaar", "Pan", "Gstin", "PaymentCard", "IndianMobile", "Email", "BankAccount"];
    static readonly Regex Host = new(@"^(?=.{1,253}$)(?!-)[a-z0-9-]{1,63}(?<!-)(\.(?!-)[a-z0-9-]{1,63}(?<!-))+$", RegexOptions.CultureInvariant);
    static readonly Regex ChromiumId = new("^[a-p]{32}$", RegexOptions.CultureInvariant);
    static readonly Regex Uuid = new("^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", RegexOptions.CultureInvariant);
    static readonly Regex SlackId = new("^[TE][A-Z0-9]{6,20}$", RegexOptions.CultureInvariant);
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
        if (ExtensionInstall is not ("store" or "manual")) problems.Add("extension install must be store or manual");
        if (ManualInstall)
        {
            if (FirefoxExtensionUrl is not null) problems.Add("a manually installed extension has no install URL");
            if (ExtensionDeveloperModeOff) problems.Add("installing the extension by hand needs developer mode");
        }
        else if (FirefoxExtensionId is not null != FirefoxExtensionUrl is not null)
            problems.Add("Firefox extension needs both an ID and an install URL");
        if (FirefoxExtensionUrl is { } u &&
            !(Uri.TryCreate(u, UriKind.Absolute, out var uri) && uri.Scheme == Uri.UriSchemeHttps && u.Length <= 500))
            problems.Add("Firefox extension URL must be https");
        if (!Modes.Contains(GuardMode)) problems.Add($"guard mode '{Trim(GuardMode)}' is not log, warn, justify, redact, approve or block");
        if (GuardWatchedSites.Count > MaxSites) problems.Add($"too many watched sites (max {MaxSites})");
        problems.AddRange(GuardWatchedSites.Where(h => !Host.IsMatch(h ?? "")).Select(h => $"watched site '{Trim(h)}' is not a host name"));
        problems.AddRange(GuardIgnoreKinds.Where(k => !Kinds.Contains(k)).Select(k => $"'{Trim(k)}' is not a kind of finding"));
        if (GuardKeywords.Count > MaxKeywords) problems.Add($"too many keywords (max {MaxKeywords})");
        if (GuardKeywords.Any(k => string.IsNullOrWhiteSpace(k) || k.Length > 100)) problems.Add("keywords must be 1–100 characters");
        // These become request headers: only IDs of the expected shape, never anything else.
        if (MicrosoftTenantId is not null != MicrosoftPolicyId is not null) problems.Add("Microsoft needs a tenant ID and a policy ID");
        if (MicrosoftOnWindows && MicrosoftTenantId is null) problems.Add("Windows tenant restrictions need the Microsoft tenant ID and policy ID");
        if (!UsbModes.Contains(UsbMode)) problems.Add($"USB mode '{Trim(UsbMode)}' is not off, read_only, encrypted_only, on_request, block or company_drives");
        if (UsbApprovedDrives.Count > MaxApprovedDrives) problems.Add($"too many approved drives (max {MaxApprovedDrives})");
        if (UsbApprovedDrives.Any(d => !DriveId.IsMatch(d ?? ""))) problems.Add("an approved drive is not a USB drive's device ID");
        // A drive without a serial gets an ID Windows makes up ("7&1a2b3c4d&0"): any drive of the
        // same model in the same port would share it, so it cannot stand for one drive (review 3b L2).
        if (UsbApprovedDrives.Any(d => d is not null && d.LastIndexOf('\\') is var i && i >= 0 && d.Length > i + 2 && d[i + 2] == '&'))
            problems.Add("an approved drive has no serial number of its own");
        if (new[] { MicrosoftTenantId, MicrosoftPolicyId }.Any(v => v is not null && !Uuid.IsMatch(v))) problems.Add("Microsoft ID is malformed");
        foreach (var (name, list) in new[] { ("Claude organization", ClaudeOrgIds), ("ChatGPT workspace", ChatGptWorkspaceIds) })
        {
            if (list.Count > MaxAccountIds) problems.Add($"too many {name} IDs (max {MaxAccountIds})");
            if (list.Any(v => !Uuid.IsMatch(v ?? ""))) problems.Add($"{name} ID is malformed");
        }
        if (SlackRequesterId is not null != SlackAllowedIds.Count > 0) problems.Add("Slack needs the org's own ID and the allowed IDs");
        if (SlackAllowedIds.Count > MaxAccountIds) problems.Add($"too many Slack IDs (max {MaxAccountIds})");
        if (SlackAllowedIds.Append(SlackRequesterId ?? "T0000000").Any(v => !SlackId.IsMatch(v ?? ""))) problems.Add("Slack ID is malformed");
        if (ExtensionAllowlist.Count > MaxAllowedExtensions) problems.Add($"too many allowed extensions (max {MaxAllowedExtensions})");
        if (ExtensionAllowlist.Any(x => !ChromiumId.IsMatch(x ?? "") && !FirefoxId.IsMatch(x ?? "")))
            problems.Add("an allowed extension ID is not a Chrome, Edge or Firefox extension ID");
        return problems;
    }

    static string Trim(string? s) => (s ?? "").Length > 60 ? s![..60] + "…" : s ?? "";
}

/// <summary>Where a report comes from. <see cref="Scanner"/> is not a browser: it is E4's
/// firewall block on the native host, reported beside the browsers it serves. Nor is
/// <see cref="Windows"/>: it is Windows' own tenant restrictions setting (D2). <see cref="Usb"/> and
/// <see cref="UsbEncryption"/> are Windows' removable-storage and BitLocker To Go policies (C3).</summary>
public enum Browser { Chrome, Edge, Firefox, Scanner, Windows, Usb, UsbEncryption, UsbDevices }

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
            if (!p.ManualInstall)
                v["ExtensionInstallForcelist"] = new[] { $"{id};{(edge ? EdgeStore : ChromeStore)}" };
            v[$@"3rdparty\extensions\{id}\policy"] = GuardSettings(p);
            // Only machine-wide native hosts: otherwise a user could register their own
            // com.savio.guard under HKCU, which the browser prefers, and answer "nothing found"
            // to every check (security review H1).
            v["NativeMessagingUserLevelHosts"] = 0;
            if (p.CompanyAccountsLocked)
            {
                // Review 3b M2: no window without SAVIO's extension, and no other extension that
                // could strip the company-accounts headers, except those the admin allows.
                v[edge ? "InPrivateModeAvailability" : "IncognitoModeAvailability"] = 1;
                v["BrowserGuestModeEnabled"] = 0;
                v["ExtensionInstallBlocklist"] = new[] { "*" };
                v["ExtensionInstallAllowlist"] = p.ExtensionAllowlist.Where(x => ChromiumIdRx.IsMatch(x))
                                                  .Prepend(id).Distinct().ToArray();
            }
        }
        return v;
    }

    static readonly System.Text.RegularExpressions.Regex ChromiumIdRx = new("^[a-p]{32}$");

    /// <summary>D3: the extension's managed settings, named as in extension/managed_schema.json.</summary>
    static Dictionary<string, object> GuardSettings(BrowserPolicy p)
    {
        var s = new Dictionary<string, object>
        {
            ["mode"] = p.GuardMode,
            ["watchedSites"] = p.GuardWatchedSites.ToArray(),
            ["ignoreKinds"] = p.GuardIgnoreKinds.ToArray(),
            ["keywords"] = p.GuardKeywords.ToArray(),
        };
        if (p.ReadPdfs) s["readPdf"] = true;
        // D2: only what is set, so an org without them sees no change to its settings.
        if (p.MicrosoftTenantId is not null) s["microsoftTenant"] = $"{p.MicrosoftTenantId}:{p.MicrosoftPolicyId}";
        if (p.ClaudeOrgIds.Count > 0) s["claudeOrgs"] = p.ClaudeOrgIds.ToArray();
        if (p.ChatGptWorkspaceIds.Count > 0) s["chatgptWorkspaces"] = p.ChatGptWorkspaceIds.ToArray();
        if (p.SlackRequesterId is not null)
        {
            s["slackRequester"] = p.SlackRequesterId;
            s["slackAllowed"] = p.SlackAllowedIds.ToArray();
        }
        return s;
    }

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
        if (p.FirefoxExtensionId is not null && (p.FirefoxExtensionUrl is not null || p.ManualInstall))
        {
            var settings = new Dictionary<string, object>(StringComparer.Ordinal);
            if (!p.ManualInstall)
                settings[p.FirefoxExtensionId] = new Dictionary<string, object>
                {
                    ["installation_mode"] = "force_installed",
                    ["install_url"] = p.FirefoxExtensionUrl!,
                };
            if (p.CompanyAccountsLocked)
            {
                // Review 3b M2: no private window without SAVIO's extension, and every other
                // extension blocked except the Firefox IDs the admin allows.
                v["DisablePrivateBrowsing"] = true;
                settings["*"] = new Dictionary<string, object> { ["installation_mode"] = "blocked" };
                settings.TryAdd(p.FirefoxExtensionId, new Dictionary<string, object> { ["installation_mode"] = "allowed" });
                foreach (var x in p.ExtensionAllowlist.Where(x => !ChromiumIdRx.IsMatch(x)))
                    settings.TryAdd(x, new Dictionary<string, object> { ["installation_mode"] = "allowed" });
            }
            if (settings.Count > 0) v["ExtensionSettings"] = settings;
            v[$@"3rdparty\Extensions\{p.FirefoxExtensionId}"] = GuardSettings(p);
        }
        return v;
    }

    static IEnumerable<string> Patterns(string host) => new[] { $"*://{host}/*", $"*://*.{host}/*" };

    /// <summary>
    /// D2 on the PC: Windows' tenant restrictions v2 ("Cloud Policy Details", TenantRestrictions.admx),
    /// read by Office apps and Edge. Only the two IDs. Never <c>enforceFirewall</c>: Microsoft warns
    /// that without a matching App Control policy it cuts every app off from Microsoft's services.
    /// </summary>
    // Windows' Removable Storage Access classes (RemovableStorage.admx): removable disks, and the
    // two classes phones and cameras use (WPD/MTP), which a "USB" rule must cover too.
    const string Disks = "{53f5630d-b6bf-11d0-94f2-00a0c91efb8b}";
    static readonly string[] Phones = ["{6AC27878-A6FA-4155-BA85-F98F491D4F33}", "{F33FDC04-D1AC-4E8E-9A30-19BBD4B108AE}"];

    /// <summary>C3: values under HKLM\SOFTWARE\Policies\Microsoft\Windows\RemovableStorageDevices.</summary>
    public static IReadOnlyDictionary<string, object> Usb(BrowserPolicy p, DateTime nowUtc)
    {
        var mode = p.UsbMode != "on_request" ? p.UsbMode : p.UsbWriteUntil > nowUtc ? "off" : "read_only";
        var v = new Dictionary<string, object>(StringComparer.OrdinalIgnoreCase);
        switch (mode)
        {
            case "block":
                v["Deny_All"] = 1;
                break;
            case "read_only":
                v[$@"{Disks}\Deny_Write"] = 1;
                foreach (var c in Phones) v[$@"{c}\Deny_Write"] = 1;
                break;
            case "encrypted_only":   // drives through BitLocker (UsbEncryption); phones cannot be encrypted
            case "company_drives":   // drives through device installation (UsbDevices); phones are not company drives
                foreach (var c in Phones) v[$@"{c}\Deny_Write"] = 1;
                break;
        }
        return v;
    }

    /// <summary>C3: "Deny write access to removable drives not protected by BitLocker"
    /// (VolumeEncryption.admx), under HKLM\SYSTEM\CurrentControlSet\Policies\Microsoft\FVE.</summary>
    public static IReadOnlyDictionary<string, object> UsbEncryption(BrowserPolicy p) =>
        p.UsbMode == "encrypted_only"
            ? new Dictionary<string, object>(StringComparer.OrdinalIgnoreCase) { ["RDVDenyWriteAccess"] = 1 }
            : new Dictionary<string, object>();

    public static IReadOnlyDictionary<string, object> Windows(BrowserPolicy p) =>
        p.MicrosoftOnWindows && p.MicrosoftTenantId is { } tid && p.MicrosoftPolicyId is { } pid
            ? new Dictionary<string, object>(StringComparer.OrdinalIgnoreCase) { ["tenantid"] = tid, ["policyid"] = pid }
            : new Dictionary<string, object>();
}
