using System.Text.Json.Nodes;
using AstraAgent.Service.Guard;
using Microsoft.Win32;
using Xunit;

namespace AstraAgent.Service.Tests;

/// <summary>
/// Phase 3 · D10 browser policies. These tests run against the real registry, under a
/// throwaway HKCU key, never HKLM and never the real browser policy keys, and against a temp
/// folder for Firefox.
///
/// The rules under test:
/// <list type="bullet">
/// <item>SAVIO changes only what it set.</item>
/// <item>Someone else's policy is never overwritten.</item>
/// <item>Drift is repaired and reported.</item>
/// <item>A bad policy is refused before anything is written.</item>
/// </list>
/// </summary>
public sealed class BrowserPolicyWriterTests : IDisposable
{
    readonly string _sandbox = $@"Software\SavioTests\{Guid.NewGuid():N}";
    readonly RegistryKey _root;
    readonly string _ffDir = Path.Combine(Path.GetTempPath(), "savio-ff-" + Guid.NewGuid().ToString("N"));

    public BrowserPolicyWriterTests() => _root = Registry.CurrentUser.CreateSubKey(_sandbox, writable: true);

    public void Dispose()
    {
        _root.Dispose();
        Registry.CurrentUser.DeleteSubKeyTree(_sandbox, false);
        using (var parent = Registry.CurrentUser.OpenSubKey(@"Software\SavioTests"))
            if (parent is { SubKeyCount: 0, ValueCount: 0 })
                try { Registry.CurrentUser.DeleteSubKey(@"Software\SavioTests", false); } catch (IOException) { }   // a parallel test still has one
        if (Directory.Exists(_ffDir)) Directory.Delete(_ffDir, true);
    }

    static readonly BrowserPolicy Full = new()
    {
        IncognitoOff = true, ExtensionDeveloperModeOff = true, NewProfilesOff = true,
        BlockedSites = ["example.com", "files.example.org"], AllowedSites = ["intranet.acme.in"],
        GoogleAllowedDomains = ["acme.in"],
        ChromeExtensionId = "abcdefghijklmnopabcdefghijklmnop",
    };

    RegistryKey Policy(Browser b) => _root.OpenSubKey(BrowserPolicyWriter.ChromiumPolicyPath(b))!;

    ApplyReport Chrome(BrowserPolicy p) =>
        BrowserPolicyWriter.ApplyChromium(_root, Browser.Chrome, BrowserPolicyMap.Chromium(p, Browser.Chrome));

    [Fact]
    public void Applies_and_records_ownership()
    {
        var r = Chrome(Full);
        Assert.Null(r.Error);
        Assert.Contains("IncognitoModeAvailability", r.Set);
        using var pol = Policy(Browser.Chrome);
        Assert.Equal(1, pol.GetValue("IncognitoModeAvailability"));
        Assert.Equal(1, pol.GetValue("ExtensionDeveloperModeSettings"));
        Assert.Equal(0, pol.GetValue("BrowserAddPersonEnabled"));
        Assert.Equal("acme.in", pol.GetValue("AllowedDomainsForApps"));
        using (var block = pol.OpenSubKey("URLBlocklist")!)
            Assert.Equal(new object[] { "example.com", "files.example.org" }, new[] { block.GetValue("1"), block.GetValue("2") });
        using (var force = pol.OpenSubKey("ExtensionInstallForcelist")!)
            Assert.Equal("abcdefghijklmnopabcdefghijklmnop;https://clients2.google.com/service/update2/crx", force.GetValue("1"));

        Assert.False(Chrome(Full).Changed);                    // idempotent
    }

    [Fact]
    public void Never_overwrites_someone_elses_policy()
    {
        using (var pol = _root.CreateSubKey(BrowserPolicyWriter.ChromiumPolicyPath(Browser.Chrome), true))
        {
            pol.SetValue("IncognitoModeAvailability", 0, RegistryValueKind.DWord);   // an org's own GPO
            using var other = pol.CreateSubKey("LocalNetworkAccessAllowedForUrls", true);
            other.SetValue("1", "http://printer.local");
        }
        var r = Chrome(Full);
        Assert.Equal(["IncognitoModeAvailability"], r.Conflicts);
        using var after = Policy(Browser.Chrome);
        Assert.Equal(0, after.GetValue("IncognitoModeAvailability"));
        using var kept = after.OpenSubKey("LocalNetworkAccessAllowedForUrls")!;
        Assert.Equal("http://printer.local", kept.GetValue("1"));

        // Dropping everything removes only what SAVIO set.
        var removed = Chrome(new BrowserPolicy());
        Assert.DoesNotContain("IncognitoModeAvailability", removed.Removed);
        using var final = Policy(Browser.Chrome);
        Assert.Equal(0, final.GetValue("IncognitoModeAvailability"));
        Assert.NotNull(final.OpenSubKey("LocalNetworkAccessAllowedForUrls"));
        Assert.Null(final.OpenSubKey("URLBlocklist"));
    }

    [Fact]
    public void Repairs_tampering_and_reports_it()
    {
        Chrome(Full);
        using (var pol = _root.OpenSubKey(BrowserPolicyWriter.ChromiumPolicyPath(Browser.Chrome), true)!)
        {
            pol.DeleteValue("IncognitoModeAvailability");             // a local admin turns incognito back on
            using var block = pol.OpenSubKey("URLBlocklist", true)!;
            block.SetValue("1", "nothing.invalid");                    // and edits the block list
        }
        var r = Chrome(Full);
        Assert.Null(r.Error);
        Assert.Equal(["IncognitoModeAvailability", "URLBlocklist"], r.Repaired.OrderBy(x => x));
        using var after = Policy(Browser.Chrome);
        Assert.Equal(1, after.GetValue("IncognitoModeAvailability"));
    }

    [Fact]
    public void Shrinking_the_policy_removes_what_is_no_longer_wanted()
    {
        Chrome(Full);
        var r = Chrome(Full with { BlockedSites = [], ChromeExtensionId = null });
        Assert.Equal(["ExtensionInstallForcelist", "URLBlocklist"], r.Removed.OrderBy(x => x));
        using var pol = Policy(Browser.Chrome);
        Assert.Null(pol.OpenSubKey("URLBlocklist"));
        Assert.Equal(1, pol.GetValue("IncognitoModeAvailability"));

        Chrome(new BrowserPolicy());
        Assert.Null(_root.OpenSubKey(@"SOFTWARE\SAVIO\BrowserPolicy\Chrome"));   // nothing owned, no marker left
    }

    [Fact]
    public void Edge_uses_its_own_names()
    {
        var map = BrowserPolicyMap.Chromium(Full with { EdgeExtensionId = "ponmlkjihgfedcbaponmlkjihgfedcba" }, Browser.Edge);
        Assert.True(map.ContainsKey("InPrivateModeAvailability"));
        Assert.True(map.ContainsKey("BrowserAddProfileEnabled"));
        Assert.False(map.ContainsKey("IncognitoModeAvailability"));
        Assert.EndsWith("edge.microsoft.com/extensionwebstorebase/v1/crx", ((string[])map["ExtensionInstallForcelist"])[0]);
        Assert.Null(BrowserPolicyWriter.ApplyChromium(_root, Browser.Edge, map).Error);
    }

    [Theory]
    [InlineData("bad host!")]
    [InlineData("http://example.com")]
    [InlineData("-example.com")]
    [InlineData("localhost")]
    public void A_bad_site_is_refused(string site)
    {
        Assert.NotEmpty((Full with { BlockedSites = [site] }).Validate());
    }

    [Fact]
    public void Bad_extension_settings_are_refused()
    {
        Assert.NotEmpty((Full with { ChromeExtensionId = "not-an-id" }).Validate());
        Assert.NotEmpty(new BrowserPolicy { FirefoxExtensionId = "savio@savio.app" }.Validate());   // no URL
        Assert.NotEmpty(new BrowserPolicy { FirefoxExtensionId = "savio@savio.app", FirefoxExtensionUrl = "http://x.in/a.xpi" }.Validate());
        Assert.Empty(Full.Validate());
    }

    // ── Firefox ───────────────────────────────────────────────────────────────────────────

    ApplyReport Firefox(BrowserPolicy p) => BrowserPolicyWriter.ApplyFirefox(_ffDir, BrowserPolicyMap.Firefox(p));

    JsonObject Policies() => (JsonNode.Parse(File.ReadAllText(Path.Combine(_ffDir, "policies.json")))!["policies"] as JsonObject)!;

    [Fact]
    public void Firefox_policies_merge_with_an_orgs_own_file()
    {
        Directory.CreateDirectory(_ffDir);
        File.WriteAllText(Path.Combine(_ffDir, "policies.json"),
            """{"policies": {"DisableTelemetry": true, "DisablePrivateBrowsing": false}}""");
        var p = Full with { DevToolsOff = true, FirefoxExtensionId = "savio@savio.app", FirefoxExtensionUrl = "https://savio.app/ext/savio.xpi" };
        var r = Firefox(p);
        Assert.Null(r.Error);
        Assert.Equal(["DisablePrivateBrowsing"], r.Conflicts);                // theirs, kept
        var pol = Policies();
        Assert.True(pol["DisableTelemetry"]!.GetValue<bool>());
        Assert.False(pol["DisablePrivateBrowsing"]!.GetValue<bool>());
        Assert.True(pol["DisableDeveloperTools"]!.GetValue<bool>());
        Assert.Contains("*://*.example.com/*", pol["WebsiteFilter"]!["Block"]!.AsArray().Select(n => n!.GetValue<string>()));
        Assert.Equal("force_installed", pol["ExtensionSettings"]!["savio@savio.app"]!["installation_mode"]!.GetValue<string>());

        Assert.False(Firefox(p).Changed);
        var cleared = Firefox(new BrowserPolicy());
        Assert.Contains("ExtensionSettings", cleared.Removed);
        Assert.True(Policies()["DisableTelemetry"]!.GetValue<bool>());       // still theirs
        Assert.False(File.Exists(Path.Combine(_ffDir, "savio-owned.json")));
    }

    [Fact]
    public void A_broken_firefox_policy_file_is_left_alone()
    {
        Directory.CreateDirectory(_ffDir);
        var path = Path.Combine(_ffDir, "policies.json");
        File.WriteAllText(path, "{ not json");
        var r = Firefox(Full);
        Assert.NotNull(r.Error);
        Assert.Equal("{ not json", File.ReadAllText(path));
    }
}
