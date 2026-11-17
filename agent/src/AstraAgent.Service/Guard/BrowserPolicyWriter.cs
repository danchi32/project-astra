using System.Text.Json;
using System.Text.Json.Nodes;
using Microsoft.Win32;

namespace AstraAgent.Service.Guard;

/// <summary>What one apply did. "Repaired" is drift: a policy SAVIO had set was found changed
/// or deleted and was put back. "Conflicts" are policies someone else already sets (a GPO,
/// another tool): SAVIO leaves them alone and says so.</summary>
public sealed record ApplyReport(
    Browser Browser,
    IReadOnlyList<string> Set,
    IReadOnlyList<string> Repaired,
    IReadOnlyList<string> Removed,
    IReadOnlyList<string> Conflicts,
    string? Error)
{
    public bool Changed => Set.Count + Repaired.Count + Removed.Count > 0;
}

/// <summary>
/// Phase 3 · D10: writes browser policies, owning only what it wrote.
///
/// SAVIO keeps a list of the policy names it set: the "Owned" value under
/// <c>SOFTWARE\SAVIO\BrowserPolicy\&lt;browser&gt;</c> for Chrome and Edge, and
/// <c>savio-owned.json</c> beside Firefox's policies.json. Only those names are ever changed or
/// removed. A policy that is already present and not on that list belongs to someone else,
/// such as an organization's own GPO or another tool (this laptop already carries one,
/// <c>LocalNetworkAccessAllowedForUrls</c>). It is reported as a conflict and never
/// overwritten.
///
/// Applying is idempotent and meant to run every cycle. A local administrator can delete the
/// keys; the next apply puts them back and reports the drift. Every write is read back. A
/// setting that does not stick is an error, never a silent success, because the admin must
/// not believe a lock is on when it is not.
/// </summary>
public static class BrowserPolicyWriter
{
    const string OwnedValue = "Owned";

    public static string ChromiumPolicyPath(Browser b) => b switch
    {
        Browser.Chrome => @"SOFTWARE\Policies\Google\Chrome",
        Browser.Edge => @"SOFTWARE\Policies\Microsoft\Edge",
        _ => throw new ArgumentException("not a Chromium browser", nameof(b)),
    };

    static string OwnershipPath(Browser b) => $@"SOFTWARE\SAVIO\BrowserPolicy\{b}";

    /// <summary>Production entry point: validate, then apply to Chrome, Edge and every Firefox install.</summary>
    public static IReadOnlyList<ApplyReport> Apply(BrowserPolicy policy)
    {
        var problems = policy.Validate();
        if (problems.Count > 0)
            return new[] { Browser.Chrome, Browser.Edge, Browser.Firefox }
                .Select(b => new ApplyReport(b, [], [], [], [], "Policy refused: " + string.Join("; ", problems))).ToList();

        var reports = new List<ApplyReport>
        {
            WithHost(ApplyChromium(Registry.LocalMachine, Browser.Chrome, BrowserPolicyMap.Chromium(policy, Browser.Chrome)),
                     policy.ChromeExtensionId),
            WithHost(ApplyChromium(Registry.LocalMachine, Browser.Edge, BrowserPolicyMap.Chromium(policy, Browser.Edge)),
                     policy.EdgeExtensionId),
        };
        var firefox = BrowserPolicyMap.Firefox(policy);
        var fx = FirefoxDistributionDirs().Select(dir => ProtectedInstall(dir)
            ? ApplyFirefox(dir, firefox)
            : new ApplyReport(Browser.Firefox, [], [], [], [],
                $"Firefox is installed outside Program Files ({Path.GetDirectoryName(dir)}), where standard users can change "
                + "files. SAVIO does not write there; set Firefox's policies by Group Policy instead.")).ToList();
        // One registration per browser, however many Firefox installs: it goes on the first report.
        if (fx.Count > 0) fx[0] = WithHost(fx[0], policy.FirefoxExtensionId);
        else WithHost(new ApplyReport(Browser.Firefox, [], [], [], [], null), null);
        reports.AddRange(fx);

        // E4: while the scanner reads anything (a browser runs the extension, or D5's file scan
        // is on), it has no network.
        var exe = Path.Combine(AppContext.BaseDirectory, NativeHostRegistration.HostExe);
        var forced = ((policy.ChromeExtensionId ?? policy.EdgeExtensionId ?? policy.FirefoxExtensionId) is not null
                      || policy.DiscoveryEnabled)
                     && File.Exists(exe);
        var scanner = ScannerFirewallReport(forced ? exe : null);
        if (forced || scanner.Changed || scanner.Error is not null) reports.Add(scanner);
        return reports;
    }

    static ApplyReport ScannerFirewallReport(string? hostExe)
    {
        try
        {
            return ScannerFirewall.Apply(new WindowsFirewallRules(), hostExe, ScannerFirewall.Enforcement);
        }
        catch (Exception ex) when (ex is System.Runtime.InteropServices.COMException or UnauthorizedAccessException
                                       or InvalidOperationException or Microsoft.CSharp.RuntimeBinder.RuntimeBinderException)
        {
            return new ApplyReport(Browser.Scanner, [], [], [], [],
                hostExe is null ? null : $"Could not set the scanner's firewall rules: {ex.Message}");
        }
    }

    /// <summary>D3: register the native host for the extension this browser is forced to run,
    /// or remove the registration when none is, and fold what happened into the report.</summary>
    static ApplyReport WithHost(ApplyReport r, string? extensionId)
    {
        var exe = Path.Combine(AppContext.BaseDirectory, NativeHostRegistration.HostExe);
        var missing = extensionId is not null && !File.Exists(exe);
        try
        {
            var change = NativeHostRegistration.Apply(Registry.LocalMachine, r.Browser, missing ? null : extensionId,
                                                      exe, AppContext.BaseDirectory);
            r = change switch
            {
                HostChange.Registered => r with { Set = [.. r.Set, NativeHostRegistration.HostName] },
                HostChange.Unregistered => r with { Removed = [.. r.Removed, NativeHostRegistration.HostName] },
                _ => r,
            };
            // Someone's own com.savio.guard would win over SAVIO's: removed, and reported as tampering.
            if (extensionId is not null && NativeHostRegistration.RemoveUserLevel(Registry.Users, r.Browser).Count > 0)
                r = r with { Repaired = [.. r.Repaired, "user-level " + NativeHostRegistration.HostName] };
            return missing ? r with { Error = r.Error ?? $"{NativeHostRegistration.HostExe} is missing beside the agent; the extension cannot scan" } : r;
        }
        catch (Exception ex) when (ex is UnauthorizedAccessException or System.Security.SecurityException or IOException)
        {
            return r with { Error = r.Error ?? $"Could not register the native host: {ex.Message}" };
        }
    }

    // ── Chrome and Edge: registry ────────────────────────────────────────────────────────

    /// <summary>
    /// A policy name may be a path, such as <c>3rdparty\extensions\&lt;id&gt;\policy</c> (an
    /// extension's managed settings). The leaf is what SAVIO owns; the keys above it are shared.
    /// Other extensions' 3rdparty policies sit beside it and are never touched, and a parent
    /// left empty by a removal is pruned.
    /// </summary>
    public static ApplyReport ApplyChromium(RegistryKey root, Browser browser, IReadOnlyDictionary<string, object> desired)
    {
        List<string> set = [], repaired = [], removed = [], conflicts = [];
        try
        {
            var owned = ReadOwned(root, browser);
            using var pol = root.CreateSubKey(ChromiumPolicyPath(browser), writable: true);

            foreach (var (name, value) in desired)
            {
                if (Exists(pol, name) && !owned.Contains(name)) { conflicts.Add(name); continue; }
                if (Holds(pol, name, value)) { owned.Add(name); continue; }
                Write(pol, name, value);
                (owned.Contains(name) ? repaired : set).Add(name);
                owned.Add(name);
            }
            foreach (var name in owned.Where(n => !desired.ContainsKey(n)).ToList())
            {
                Delete(pol, name);
                owned.Remove(name);
                removed.Add(name);
            }
            WriteOwned(root, browser, owned);

            var notStuck = desired.Keys.Where(n => owned.Contains(n) && !Holds(pol, n, desired[n])).ToList();
            return new ApplyReport(browser, set, repaired, removed, conflicts,
                notStuck.Count == 0 ? null : $"Did not stick (something else rewrites them): {string.Join(", ", notStuck)}");
        }
        catch (Exception ex) when (ex is UnauthorizedAccessException or System.Security.SecurityException or IOException)
        {
            return new ApplyReport(browser, set, repaired, removed, conflicts, $"Could not write {browser} policy: {ex.Message}");
        }
    }

    /// <summary>Runs <paramref name="f"/> on the key that holds a (possibly nested) policy name,
    /// and on its leaf. Without <paramref name="create"/> a missing parent gives null.</summary>
    static T At<T>(RegistryKey pol, string name, bool create, Func<RegistryKey?, string, T> f)
    {
        var i = name.LastIndexOf('\\');
        if (i < 0) return f(pol, name);
        using var parent = create ? pol.CreateSubKey(name[..i], writable: true) : pol.OpenSubKey(name[..i], writable: true);
        return f(parent, name[(i + 1)..]);
    }

    static bool Has(RegistryKey k, string leaf) =>
        k.GetValueNames().Contains(leaf, StringComparer.OrdinalIgnoreCase) ||
        k.GetSubKeyNames().Contains(leaf, StringComparer.OrdinalIgnoreCase);

    static bool Exists(RegistryKey pol, string name) => At(pol, name, false, (k, leaf) => k is not null && Has(k, leaf));

    static bool Holds(RegistryKey pol, string name, object value) =>
        At(pol, name, false, (k, leaf) => k is not null && HoldsAt(k, leaf, value));

    static void Write(RegistryKey pol, string name, object value) =>
        At(pol, name, true, (k, leaf) => { WriteAt(k!, leaf, value); return 0; });

    static void Delete(RegistryKey pol, string name)
    {
        At(pol, name, false, (k, leaf) => { if (k is not null) DeleteAt(k, leaf); return 0; });
        // Prune the parents this left empty (3rdparty\extensions\<id>), never one holding anything else.
        for (var i = name.LastIndexOf('\\'); i > 0; i = name.LastIndexOf('\\', i - 1))
        {
            var path = name[..i];
            using (var k = pol.OpenSubKey(path))
                if (k is null || k.ValueCount + k.SubKeyCount > 0) return;
            pol.DeleteSubKey(path, false);
        }
    }

    /// <summary>Lists are subkeys with values "1".."n"; maps (an extension's managed settings)
    /// are subkeys holding each entry. Both are how Chrome and Edge read policy from the registry.</summary>
    static bool HoldsAt(RegistryKey k, string name, object value)
    {
        if (value is string[] or IReadOnlyDictionary<string, object>)
        {
            if (k.GetValueNames().Contains(name, StringComparer.OrdinalIgnoreCase)) return false;
            using var sub = k.OpenSubKey(name);
            if (sub is null) return false;
            if (value is string[] list)
                return sub.SubKeyCount == 0 && sub.ValueCount == list.Length &&
                       list.Select((item, i) => sub.GetValue((i + 1).ToString()) as string == item).All(x => x);
            var map = (IReadOnlyDictionary<string, object>)value;
            return sub.ValueCount + sub.SubKeyCount == map.Count && map.All(e => HoldsAt(sub, e.Key, e.Value));
        }
        if (k.GetSubKeyNames().Contains(name, StringComparer.OrdinalIgnoreCase)) return false;
        var current = k.GetValue(name);
        return value switch
        {
            int i => current is int c && c == i && k.GetValueKind(name) == RegistryValueKind.DWord,
            string s => current is string c && c == s,
            _ => false,
        };
    }

    static void WriteAt(RegistryKey k, string name, object value)
    {
        DeleteAt(k, name);
        switch (value)
        {
            case string[] list:
                using (var sub = k.CreateSubKey(name, writable: true))
                    for (int i = 0; i < list.Length; i++) sub.SetValue((i + 1).ToString(), list[i], RegistryValueKind.String);
                break;
            case IReadOnlyDictionary<string, object> map:
                using (var sub = k.CreateSubKey(name, writable: true))
                    foreach (var (n, v) in map) WriteAt(sub, n, v);
                break;
            case int i: k.SetValue(name, i, RegistryValueKind.DWord); break;
            case string s: k.SetValue(name, s, RegistryValueKind.String); break;
            default: throw new ArgumentException($"unsupported value for {name}");
        }
    }

    static void DeleteAt(RegistryKey k, string name)
    {
        if (k.GetSubKeyNames().Contains(name, StringComparer.OrdinalIgnoreCase)) k.DeleteSubKeyTree(name, false);
        if (k.GetValueNames().Contains(name, StringComparer.OrdinalIgnoreCase)) k.DeleteValue(name, false);
    }

    static HashSet<string> ReadOwned(RegistryKey root, Browser b)
    {
        using var k = root.OpenSubKey(OwnershipPath(b));
        return new HashSet<string>(k?.GetValue(OwnedValue) as string[] ?? [], StringComparer.OrdinalIgnoreCase);
    }

    static void WriteOwned(RegistryKey root, Browser b, HashSet<string> owned)
    {
        if (owned.Count == 0) { root.DeleteSubKeyTree(OwnershipPath(b), false); return; }
        using var k = root.CreateSubKey(OwnershipPath(b), writable: true);
        k.SetValue(OwnedValue, owned.OrderBy(x => x, StringComparer.OrdinalIgnoreCase).ToArray(), RegistryValueKind.MultiString);
    }

    // ── Firefox: distribution\policies.json ──────────────────────────────────────────────

    public static ApplyReport ApplyFirefox(string distributionDir, IReadOnlyDictionary<string, object> desired)
    {
        List<string> set = [], repaired = [], removed = [], conflicts = [];
        var file = Path.Combine(distributionDir, "policies.json");
        var ownedFile = Path.Combine(distributionDir, "savio-owned.json");
        try
        {
            JsonObject doc;
            if (File.Exists(file))
            {
                // An organization's own policies.json is kept. If it can't be read, nothing is
                // written: rewriting it would destroy their settings.
                try { doc = JsonNode.Parse(File.ReadAllText(file)) as JsonObject ?? throw new JsonException("not an object"); }
                catch (JsonException ex)
                {
                    return new ApplyReport(Browser.Firefox, [], [], [], [], $"Existing policies.json is not valid JSON, left untouched: {ex.Message}");
                }
            }
            else doc = new JsonObject();
            var policies = doc["policies"] as JsonObject ?? new JsonObject();
            doc["policies"] = policies;
            var owned = File.Exists(ownedFile)
                ? new HashSet<string>(JsonSerializer.Deserialize<string[]>(File.ReadAllText(ownedFile)) ?? [], StringComparer.Ordinal)
                : new HashSet<string>(StringComparer.Ordinal);

            foreach (var (name, value) in desired)
            {
                var node = JsonSerializer.SerializeToNode(value);
                if (FxExists(policies, name) && !owned.Contains(name)) { conflicts.Add(name); continue; }
                if (JsonNode.DeepEquals(FxGet(policies, name), node)) { owned.Add(name); continue; }
                FxSet(policies, name, node);
                (owned.Contains(name) ? repaired : set).Add(name);
                owned.Add(name);
            }
            foreach (var name in owned.Where(n => !desired.ContainsKey(n)).ToList())
            {
                FxRemove(policies, name);
                owned.Remove(name);
                removed.Add(name);
            }

            if (set.Count + repaired.Count + removed.Count > 0)
            {
                Directory.CreateDirectory(distributionDir);
                WriteAtomic(file, doc.ToJsonString(new JsonSerializerOptions { WriteIndented = true }));
            }
            if (owned.Count > 0) WriteAtomic(ownedFile, JsonSerializer.Serialize(owned.OrderBy(x => x).ToArray()));
            else if (File.Exists(ownedFile)) File.Delete(ownedFile);
            return new ApplyReport(Browser.Firefox, set, repaired, removed, conflicts, null);
        }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException or JsonException)
        {
            return new ApplyReport(Browser.Firefox, set, repaired, removed, conflicts, $"Could not write Firefox policy: {ex.Message}");
        }
    }

    // A Firefox policy name may be a path too: 3rdparty\Extensions\<id> is one extension's
    // managed settings inside the shared "3rdparty" object.

    /// <summary>Present, or blocked by someone else's non-object value on the way down.</summary>
    static bool FxExists(JsonObject policies, string name)
    {
        JsonNode? node = policies;
        foreach (var part in name.Split('\\'))
        {
            if (node is not JsonObject o) return true;
            if (!o.TryGetPropertyValue(part, out node)) return false;
        }
        return true;
    }

    static JsonNode? FxGet(JsonObject policies, string name)
    {
        JsonNode? node = policies;
        foreach (var part in name.Split('\\'))
            if (node is not JsonObject o || !o.TryGetPropertyValue(part, out node)) return null;
        return node;
    }

    static void FxSet(JsonObject policies, string name, JsonNode? value)
    {
        var parts = name.Split('\\');
        var o = policies;
        foreach (var part in parts[..^1])
        {
            if (o[part] is not JsonObject next) { next = new JsonObject(); o[part] = next; }
            o = next;
        }
        o[parts[^1]] = value;
    }

    static void FxRemove(JsonObject policies, string name)
    {
        var parts = name.Split('\\');
        var chain = new List<JsonObject> { policies };
        foreach (var part in parts[..^1])
        {
            if (chain[^1][part] is not JsonObject next) return;
            chain.Add(next);
        }
        chain[^1].Remove(parts[^1]);
        for (var i = chain.Count - 1; i > 0 && chain[i].Count == 0; i--) chain[i - 1].Remove(parts[i - 1]);
    }

    /// <summary>Write to a temp file then swap it in, so Firefox never reads half a file.</summary>
    static void WriteAtomic(string path, string content)
    {
        var tmp = path + ".savio-tmp";
        File.WriteAllText(tmp, content);
        File.Move(tmp, path, overwrite: true);
    }

    /// <summary>
    /// Security review M4: the service writes, moves and deletes files in Firefox's
    /// distribution folder as SYSTEM. In a Firefox installed where standard users can write (a
    /// folder under C:\ inherits "Authenticated Users: Modify"), a junction planted there would
    /// turn those writes into arbitrary file writes as SYSTEM. Only an install under Program
    /// Files, with no link anywhere on the way, is written to.
    /// </summary>
    internal static bool ProtectedInstall(string distributionDir)
    {
        var roots = new[] { Environment.SpecialFolder.ProgramFiles, Environment.SpecialFolder.ProgramFilesX86 }
            .Select(Environment.GetFolderPath).Where(r => r.Length > 0)
            .Select(r => r.TrimEnd('\\') + "\\");
        var full = Path.GetFullPath(distributionDir);
        if (!roots.Any(r => full.StartsWith(r, StringComparison.OrdinalIgnoreCase))) return false;
        try
        {
            for (var d = new DirectoryInfo(full); d is not null && d.FullName.Length > 3; d = d.Parent)
                if (d.Exists && (d.Attributes.HasFlag(FileAttributes.ReparsePoint) || d.LinkTarget is not null))
                    return false;
            var file = new FileInfo(Path.Combine(full, "policies.json"));
            return !(file.Exists && file.Attributes.HasFlag(FileAttributes.ReparsePoint));
        }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException) { return false; }
    }

    /// <summary>Each installed Firefox's distribution folder, from the uninstall/version keys.</summary>
    public static IEnumerable<string> FirefoxDistributionDirs()
    {
        var dirs = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (var basePath in new[] { @"SOFTWARE\Mozilla\Mozilla Firefox", @"SOFTWARE\WOW6432Node\Mozilla\Mozilla Firefox" })
        {
            using var root = Registry.LocalMachine.OpenSubKey(basePath);
            if (root is null) continue;
            foreach (var version in root.GetSubKeyNames())
            {
                using var main = root.OpenSubKey($@"{version}\Main");
                if (main?.GetValue("Install Directory") is string dir && File.Exists(Path.Combine(dir, "firefox.exe")))
                    dirs.Add(Path.Combine(dir, "distribution"));
            }
        }
        return dirs;
    }
}
