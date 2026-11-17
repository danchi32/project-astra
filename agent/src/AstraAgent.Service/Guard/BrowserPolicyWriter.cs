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
            ApplyChromium(Registry.LocalMachine, Browser.Chrome, BrowserPolicyMap.Chromium(policy, Browser.Chrome)),
            ApplyChromium(Registry.LocalMachine, Browser.Edge, BrowserPolicyMap.Chromium(policy, Browser.Edge)),
        };
        var firefox = BrowserPolicyMap.Firefox(policy);
        reports.AddRange(FirefoxDistributionDirs().Select(dir => ApplyFirefox(dir, firefox)));
        return reports;
    }

    // ── Chrome and Edge: registry ────────────────────────────────────────────────────────

    public static ApplyReport ApplyChromium(RegistryKey root, Browser browser, IReadOnlyDictionary<string, object> desired)
    {
        List<string> set = [], repaired = [], removed = [], conflicts = [];
        try
        {
            var owned = ReadOwned(root, browser);
            using var pol = root.CreateSubKey(ChromiumPolicyPath(browser), writable: true);
            var present = new HashSet<string>(pol.GetValueNames().Concat(pol.GetSubKeyNames()), StringComparer.OrdinalIgnoreCase);

            foreach (var (name, value) in desired)
            {
                if (present.Contains(name) && !owned.Contains(name)) { conflicts.Add(name); continue; }
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

    static bool Holds(RegistryKey pol, string name, object value)
    {
        if (value is string[] list)
        {
            using var sub = pol.OpenSubKey(name);
            if (sub is null || sub.ValueCount != list.Length) return false;
            return list.Select((item, i) => sub.GetValue((i + 1).ToString()) as string == item).All(x => x);
        }
        if (pol.GetSubKeyNames().Contains(name, StringComparer.OrdinalIgnoreCase)) return false;
        var current = pol.GetValue(name);
        return value switch
        {
            int i => current is int c && c == i && pol.GetValueKind(name) == RegistryValueKind.DWord,
            string s => current is string c && c == s,
            _ => false,
        };
    }

    static void Write(RegistryKey pol, string name, object value)
    {
        Delete(pol, name);
        switch (value)
        {
            case string[] list:
                using (var sub = pol.CreateSubKey(name, writable: true))
                    for (int i = 0; i < list.Length; i++) sub.SetValue((i + 1).ToString(), list[i], RegistryValueKind.String);
                break;
            case int i: pol.SetValue(name, i, RegistryValueKind.DWord); break;
            case string s: pol.SetValue(name, s, RegistryValueKind.String); break;
            default: throw new ArgumentException($"unsupported value for {name}");
        }
    }

    static void Delete(RegistryKey pol, string name)
    {
        if (pol.GetSubKeyNames().Contains(name, StringComparer.OrdinalIgnoreCase)) pol.DeleteSubKeyTree(name, false);
        if (pol.GetValueNames().Contains(name, StringComparer.OrdinalIgnoreCase)) pol.DeleteValue(name, false);
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
                if (policies.ContainsKey(name) && !owned.Contains(name)) { conflicts.Add(name); continue; }
                if (JsonNode.DeepEquals(policies[name], node)) { owned.Add(name); continue; }
                policies[name] = node;
                (owned.Contains(name) ? repaired : set).Add(name);
                owned.Add(name);
            }
            foreach (var name in owned.Where(n => !desired.ContainsKey(n)).ToList())
            {
                policies.Remove(name);
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

    /// <summary>Write to a temp file then swap it in, so Firefox never reads half a file.</summary>
    static void WriteAtomic(string path, string content)
    {
        var tmp = path + ".savio-tmp";
        File.WriteAllText(tmp, content);
        File.Move(tmp, path, overwrite: true);
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
