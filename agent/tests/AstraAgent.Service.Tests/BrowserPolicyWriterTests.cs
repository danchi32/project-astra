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
        Assert.Equal([@"3rdparty\extensions\abcdefghijklmnopabcdefghijklmnop\policy", "ExtensionInstallForcelist",
                      "NativeMessagingUserLevelHosts", "URLBlocklist"],
                     r.Removed.OrderBy(x => x, StringComparer.Ordinal));
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

    // ── D3: the extension's managed settings (3rdparty) ───────────────────────────────────

    const string ChromeId = "abcdefghijklmnopabcdefghijklmnop";
    static readonly BrowserPolicy Guarded = Full with
    {
        GuardMode = "warn", GuardWatchedSites = ["chatgpt.com"], GuardKeywords = ["project falcon"],
    };

    [Fact]
    public void Reading_pdfs_is_written_as_a_dword_and_kept()
    {
        // Found in the live test (19 Nov): readPdf is a boolean, which the writer did not know, so
        // the whole cycle threw and left the extension's settings half written.
        var r = Chrome(Guarded with { ReadPdfs = true });
        Assert.Null(r.Error);
        using (var ours = Policy(Browser.Chrome).OpenSubKey($@"3rdparty\extensions\{ChromeId}\policy")!)
        {
            Assert.Equal(1, ours.GetValue("readPdf"));
            Assert.Equal(RegistryValueKind.DWord, ours.GetValueKind("readPdf"));
        }
        Assert.False(Chrome(Guarded with { ReadPdfs = true }).Changed);   // held, not rewritten every cycle
    }

    [Fact]
    public void Extension_settings_go_under_3rdparty_beside_other_extensions()
    {
        using (var other = _root.CreateSubKey($@"{BrowserPolicyWriter.ChromiumPolicyPath(Browser.Chrome)}\3rdparty\extensions\zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz\policy", true))
            other.SetValue("theirs", 1, RegistryValueKind.DWord);   // another vendor's extension policy

        var r = Chrome(Guarded);
        Assert.Null(r.Error);
        Assert.Contains($@"3rdparty\extensions\{ChromeId}\policy", r.Set);
        using (var ours = Policy(Browser.Chrome).OpenSubKey($@"3rdparty\extensions\{ChromeId}\policy")!)
        {
            Assert.Equal("warn", ours.GetValue("mode"));
            using var sites = ours.OpenSubKey("watchedSites")!;
            Assert.Equal("chatgpt.com", sites.GetValue("1"));
            using var kinds = ours.OpenSubKey("ignoreKinds")!;
            Assert.Equal("Email", kinds.GetValue("1"));
        }
        Assert.False(Chrome(Guarded).Changed);

        // A user edits the mode back to "log": put back, reported as drift.
        using (var ours = _root.OpenSubKey($@"{BrowserPolicyWriter.ChromiumPolicyPath(Browser.Chrome)}\3rdparty\extensions\{ChromeId}\policy", true)!)
            ours.SetValue("mode", "log");
        Assert.Contains($@"3rdparty\extensions\{ChromeId}\policy", Chrome(Guarded).Repaired);

        // Dropping the extension removes our branch and prunes our ID's key, never theirs.
        Chrome(new BrowserPolicy());
        using var pol = Policy(Browser.Chrome);
        Assert.Null(pol.OpenSubKey($@"3rdparty\extensions\{ChromeId}"));
        using var kept = pol.OpenSubKey(@"3rdparty\extensions\zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz\policy")!;
        Assert.Equal(1, kept.GetValue("theirs"));
    }

    [Fact]
    public void Someone_elses_settings_for_our_extension_are_a_conflict()
    {
        using (var gpo = _root.CreateSubKey($@"{BrowserPolicyWriter.ChromiumPolicyPath(Browser.Chrome)}\3rdparty\extensions\{ChromeId}\policy", true))
            gpo.SetValue("mode", "block");
        var r = Chrome(Guarded);
        Assert.Contains($@"3rdparty\extensions\{ChromeId}\policy", r.Conflicts);
        using var kept = Policy(Browser.Chrome).OpenSubKey($@"3rdparty\extensions\{ChromeId}\policy")!;
        Assert.Equal("block", kept.GetValue("mode"));
        Assert.Null(kept.GetValue("keywords"));
    }

    [Fact]
    public void Firefox_extension_settings_share_3rdparty_with_others()
    {
        Directory.CreateDirectory(_ffDir);
        File.WriteAllText(Path.Combine(_ffDir, "policies.json"),
            """{"policies": {"3rdparty": {"Extensions": {"other@vendor.com": {"x": 1}}}}}""");
        var p = Guarded with { FirefoxExtensionId = "guard@savio.app", FirefoxExtensionUrl = "https://savio.app/ext/guard.xpi" };
        var r = Firefox(p);
        Assert.Null(r.Error);
        Assert.Contains(@"3rdparty\Extensions\guard@savio.app", r.Set);
        var ext = Policies()["3rdparty"]!["Extensions"]!;
        Assert.Equal("warn", ext["guard@savio.app"]!["mode"]!.GetValue<string>());
        Assert.Equal("project falcon", ext["guard@savio.app"]!["keywords"]![0]!.GetValue<string>());
        Assert.Equal(1, ext["other@vendor.com"]!["x"]!.GetValue<int>());
        Assert.False(Firefox(p).Changed);

        Firefox(new BrowserPolicy());
        ext = Policies()["3rdparty"]!["Extensions"]!;
        Assert.Null(ext["guard@savio.app"]);
        Assert.NotNull(ext["other@vendor.com"]);

        // With nobody else there, the emptied objects go too.
        File.WriteAllText(Path.Combine(_ffDir, "policies.json"), """{"policies": {}}""");
        Firefox(p);
        Firefox(new BrowserPolicy());
        Assert.Null(Policies()["3rdparty"]);
    }

    [Theory]
    [InlineData("shout")]
    [InlineData("")]
    public void A_bad_guard_mode_is_refused(string mode) => Assert.NotEmpty((Full with { GuardMode = mode }).Validate());

    [Fact]
    public void Bad_guard_settings_are_refused()
    {
        Assert.NotEmpty((Full with { GuardIgnoreKinds = ["Passwords"] }).Validate());
        Assert.NotEmpty((Full with { GuardWatchedSites = ["https://chatgpt.com"] }).Validate());
        Assert.NotEmpty((Full with { GuardKeywords = [" "] }).Validate());
        Assert.NotEmpty((Full with { GuardKeywords = Enumerable.Range(0, 201).Select(i => $"k{i}").ToArray() }).Validate());
        Assert.Empty(Guarded.Validate());
    }

    // ── D3: native messaging host registration ────────────────────────────────────────────

    [Fact]
    public void Native_host_is_registered_for_the_forced_extension_only()
    {
        Directory.CreateDirectory(_ffDir);
        var exe = Path.Combine(_ffDir, NativeHostRegistration.HostExe);
        Assert.Equal(HostChange.Registered, NativeHostRegistration.Apply(_root, Browser.Chrome, ChromeId, exe, _ffDir));
        Assert.Equal(HostChange.Registered, NativeHostRegistration.Apply(_root, Browser.Firefox, "guard@savio.app", exe, _ffDir));
        Assert.Equal(HostChange.None, NativeHostRegistration.Apply(_root, Browser.Chrome, ChromeId, exe, _ffDir));

        string manifestPath;
        using (var k = _root.OpenSubKey(NativeHostRegistration.RegistryPath(Browser.Chrome))!)
            manifestPath = (string)k.GetValue("")!;
        var m = JsonNode.Parse(File.ReadAllText(manifestPath))!;
        Assert.Equal("com.savio.guard", m["name"]!.GetValue<string>());
        Assert.Equal(exe, m["path"]!.GetValue<string>());
        Assert.Equal("stdio", m["type"]!.GetValue<string>());
        Assert.Equal($"chrome-extension://{ChromeId}/", m["allowed_origins"]![0]!.GetValue<string>());
        using (var k = _root.OpenSubKey(NativeHostRegistration.RegistryPath(Browser.Firefox))!)
            Assert.Equal("guard@savio.app", JsonNode.Parse(File.ReadAllText((string)k.GetValue("")!))!["allowed_extensions"]![0]!.GetValue<string>());

        // Someone repoints the host at another program: put back.
        using (var k = _root.OpenSubKey(NativeHostRegistration.RegistryPath(Browser.Chrome), true)!)
            k.SetValue("", @"C:\Users\Public\evil.json");
        Assert.Equal(HostChange.Registered, NativeHostRegistration.Apply(_root, Browser.Chrome, ChromeId, exe, _ffDir));

        Assert.Equal(HostChange.Unregistered, NativeHostRegistration.Apply(_root, Browser.Chrome, null, exe, _ffDir));
        Assert.Null(_root.OpenSubKey(NativeHostRegistration.RegistryPath(Browser.Chrome)));
        Assert.False(File.Exists(manifestPath));
        Assert.Equal(HostChange.None, NativeHostRegistration.Apply(_root, Browser.Chrome, null, exe, _ffDir));
    }

    [Fact]
    public void A_users_own_host_registration_is_removed_and_user_level_hosts_are_off()
    {
        // Review H1. Chrome and Edge: ignore user-level hosts by policy, whenever the extension is forced.
        Assert.Equal(0, BrowserPolicyMap.Chromium(Full, Browser.Chrome)["NativeMessagingUserLevelHosts"]);
        Assert.False(BrowserPolicyMap.Chromium(Full with { ChromeExtensionId = null }, Browser.Chrome)
            .ContainsKey("NativeMessagingUserLevelHosts"));

        // Firefox has no such policy: a person's own registration is removed from their hive.
        // Here the sandbox stands in for HKEY_USERS, with two people and a classes hive.
        foreach (var sid in new[] { "S-1-5-21-1-2-3-1001", "S-1-5-21-1-2-3-1002", "S-1-5-21-1-2-3-1001_Classes", ".DEFAULT" })
            _root.CreateSubKey(sid).Dispose();
        using (var planted = _root.CreateSubKey($@"S-1-5-21-1-2-3-1001\{NativeHostRegistration.RegistryPath(Browser.Firefox)}"))
            planted.SetValue("", @"C:\Users\x\fake-host.json");
        using (var other = _root.CreateSubKey($@"S-1-5-21-1-2-3-1002\SOFTWARE\Mozilla\NativeMessagingHosts\some.other.host"))
            other.SetValue("", "x");

        Assert.Equal(["S-1-5-21-1-2-3-1001"], NativeHostRegistration.RemoveUserLevel(_root, Browser.Firefox));
        Assert.Null(_root.OpenSubKey($@"S-1-5-21-1-2-3-1001\{NativeHostRegistration.RegistryPath(Browser.Firefox)}"));
        Assert.NotNull(_root.OpenSubKey(@"S-1-5-21-1-2-3-1002\SOFTWARE\Mozilla\NativeMessagingHosts\some.other.host"));   // not ours
        Assert.Empty(NativeHostRegistration.RemoveUserLevel(_root, Browser.Firefox));
    }

    [Fact]
    public void A_manual_install_sets_everything_but_the_force_install()
    {
        var manual = Full with { ExtensionInstall = "manual", ExtensionDeveloperModeOff = false };
        Assert.Empty(manual.Validate());
        var chrome = BrowserPolicyMap.Chromium(manual, Browser.Chrome);
        Assert.False(chrome.ContainsKey("ExtensionInstallForcelist"));   // a browser refuses a hand-installed force-listed ID
        Assert.True(chrome.ContainsKey($@"3rdparty\extensions\{ChromeId}\policy"));
        Assert.Equal(0, chrome["NativeMessagingUserLevelHosts"]);

        var ff = BrowserPolicyMap.Firefox(manual with { FirefoxExtensionId = "guard@savio.app" });
        Assert.False(ff.ContainsKey("ExtensionSettings"));
        Assert.True(ff.ContainsKey(@"3rdparty\Extensions\guard@savio.app"));

        Assert.NotEmpty((manual with { ExtensionDeveloperModeOff = true }).Validate());
        Assert.NotEmpty((manual with { FirefoxExtensionId = "guard@savio.app", FirefoxExtensionUrl = "https://addons.mozilla.org/x.xpi" }).Validate());
        Assert.NotEmpty((Full with { ExtensionInstall = "sideload" }).Validate());
    }

    [Fact]
    public void Company_account_ids_go_to_the_extension_only_when_set_and_only_as_ids()
    {
        const string tid = "aaaabbbb-0000-cccc-1111-dddd2222eeee", pid = "1aaaaaa1-2bb2-3cc3-4dd4-5eeeeeeeeee5";
        var accounts = Full with
        {
            MicrosoftTenantId = tid, MicrosoftPolicyId = pid, ClaudeOrgIds = [tid], ChatGptWorkspaceIds = [pid],
            SlackRequesterId = "E0123ABCD", SlackAllowedIds = ["E0123ABCD", "T0456EFGH"],
        };
        Assert.Empty(accounts.Validate());
        var settings = (IReadOnlyDictionary<string, object>)BrowserPolicyMap.Chromium(accounts, Browser.Chrome)[$@"3rdparty\extensions\{ChromeId}\policy"];
        Assert.Equal($"{tid}:{pid}", settings["microsoftTenant"]);
        Assert.Equal(new[] { "E0123ABCD", "T0456EFGH" }, settings["slackAllowed"]);
        var plain = (IReadOnlyDictionary<string, object>)BrowserPolicyMap.Chromium(Full, Browser.Chrome)[$@"3rdparty\extensions\{ChromeId}\policy"];
        Assert.False(plain.ContainsKey("microsoftTenant") || plain.ContainsKey("claudeOrgs") || plain.ContainsKey("slackRequester"));
        // PDFs are read only where the org chose it; otherwise the setting is not there at all.
        Assert.False(plain.ContainsKey("readPdf"));
        var pdf = (IReadOnlyDictionary<string, object>)BrowserPolicyMap.Chromium(Full with { ReadPdfs = true }, Browser.Chrome)[$@"3rdparty\extensions\{ChromeId}\policy"];
        Assert.Equal(true, pdf["readPdf"]);

        // They become request headers: anything but an ID is refused, including a smuggled header.
        Assert.NotEmpty((accounts with { MicrosoftPolicyId = null }).Validate());
        Assert.NotEmpty((accounts with { ClaudeOrgIds = [tid + "\r\nX-Evil: 1"] }).Validate());
        Assert.NotEmpty((accounts with { SlackRequesterId = "E0123ABCD,T999" }).Validate());
        Assert.NotEmpty((accounts with { SlackAllowedIds = [] }).Validate());
        Assert.NotEmpty((accounts with { ChatGptWorkspaceIds = Enumerable.Repeat(pid, 51).ToList() }).Validate());
    }

    [Fact]
    public void Windows_tenant_restrictions_are_the_two_ids_all_or_nothing()
    {
        const string tid = "aaaabbbb-0000-cccc-1111-dddd2222eeee", pid = "1aaaaaa1-2bb2-3cc3-4dd4-5eeeeeeeeee5";
        var on = new BrowserPolicy { MicrosoftTenantId = tid, MicrosoftPolicyId = pid, MicrosoftOnWindows = true };
        Assert.Empty(on.Validate());
        Assert.NotEmpty(new BrowserPolicy { MicrosoftOnWindows = true }.Validate());          // needs the IDs
        Assert.Empty(BrowserPolicyMap.Windows(on with { MicrosoftOnWindows = false }));       // the extension's only

        // Never used here: nothing is created.
        var none = BrowserPolicyWriter.ApplyWindows(_root, BrowserPolicyMap.Windows(new BrowserPolicy()));
        Assert.False(none.Changed);
        Assert.Null(_root.OpenSubKey(BrowserPolicyWriter.WindowsPayloadPath));

        var r = BrowserPolicyWriter.ApplyWindows(_root, BrowserPolicyMap.Windows(on));
        Assert.Equal(["policyid", "tenantid"], r.Set.Order());
        using (var k = _root.OpenSubKey(BrowserPolicyWriter.WindowsPayloadPath)!)
        {
            Assert.Equal(tid, k.GetValue("tenantid"));
            Assert.Equal(RegistryValueKind.String, k.GetValueKind("policyid"));
            Assert.Null(k.GetValue("enforceFirewall"));                                     // never: it cuts apps off
        }
        using (var k = _root.OpenSubKey(BrowserPolicyWriter.WindowsPayloadPath, true)!) k.DeleteValue("policyid");
        Assert.Equal(["policyid"], BrowserPolicyWriter.ApplyWindows(_root, BrowserPolicyMap.Windows(on)).Repaired);

        // Turned off: SAVIO's values go, and the keys they leave empty.
        Assert.Equal(2, BrowserPolicyWriter.ApplyWindows(_root, BrowserPolicyMap.Windows(new BrowserPolicy())).Removed.Count);
        Assert.Null(_root.OpenSubKey(@"SOFTWARE\Policies\Microsoft\Windows\TenantRestrictions"));

        // Intune or a GPO already sets it (even only part of it): left entirely alone, reported.
        using (var gpo = _root.CreateSubKey(BrowserPolicyWriter.WindowsPayloadPath, true)) gpo.SetValue("tenantid", "their-tenant");
        var c = BrowserPolicyWriter.ApplyWindows(_root, BrowserPolicyMap.Windows(on));
        Assert.Equal(["policyid", "tenantid"], c.Conflicts);
        Assert.False(c.Changed);
        using (var k = _root.OpenSubKey(BrowserPolicyWriter.WindowsPayloadPath)!)
        {
            Assert.Equal("their-tenant", k.GetValue("tenantid"));
            Assert.Null(k.GetValue("policyid"));
        }
    }

    [Fact]
    public void Usb_modes_are_windows_own_policies_and_unused_keys_are_never_created()
    {
        var now = new DateTime(2026, 11, 19, 9, 0, 0, DateTimeKind.Utc);
        BrowserPolicy Mode(string m, DateTime? until = null) => new() { UsbMode = m, UsbWriteUntil = until };
        Assert.NotEmpty(Mode("everything").Validate());
        Assert.Empty(BrowserPolicyMap.Usb(Mode("off"), now));
        Assert.Equal(["Deny_All"], BrowserPolicyMap.Usb(Mode("block"), now).Keys);
        var readOnly = BrowserPolicyMap.Usb(Mode("read_only"), now);
        Assert.Equal(3, readOnly.Count);                                                  // drives and both phone classes
        Assert.Contains(@"{53f5630d-b6bf-11d0-94f2-00a0c91efb8b}\Deny_Write", readOnly.Keys);
        Assert.Equal(readOnly.Keys, BrowserPolicyMap.Usb(Mode("on_request"), now).Keys);  // read-only outside a window
        Assert.Empty(BrowserPolicyMap.Usb(Mode("on_request", now.AddMinutes(5)), now));   // writing inside it
        Assert.Equal(2, BrowserPolicyMap.Usb(Mode("encrypted_only"), now).Count);         // phones; drives via BitLocker
        Assert.Equal(["RDVDenyWriteAccess"], BrowserPolicyMap.UsbEncryption(Mode("encrypted_only")).Keys);
        Assert.Empty(BrowserPolicyMap.UsbEncryption(Mode("block")));

        // Never used: nothing is created, not even the key.
        Assert.False(BrowserPolicyWriter.ApplyIfUsed(_root, Browser.UsbEncryption, BrowserPolicyMap.UsbEncryption(Mode("off"))).Changed);
        Assert.Null(_root.OpenSubKey(BrowserPolicyWriter.ChromiumPolicyPath(Browser.UsbEncryption)));

        var r = BrowserPolicyWriter.ApplyIfUsed(_root, Browser.Usb, readOnly);
        Assert.Equal(3, r.Set.Count);
        using (var k = _root.OpenSubKey($@"{BrowserPolicyWriter.ChromiumPolicyPath(Browser.Usb)}\{{53f5630d-b6bf-11d0-94f2-00a0c91efb8b}}")!)
            Assert.Equal(1, k.GetValue("Deny_Write"));
        // A window opens: the values go; it ends: they come back as set, not as tampering.
        Assert.Equal(3, BrowserPolicyWriter.ApplyIfUsed(_root, Browser.Usb, BrowserPolicyMap.Usb(Mode("on_request", now.AddMinutes(5)), now)).Removed.Count);
        var back = BrowserPolicyWriter.ApplyIfUsed(_root, Browser.Usb, BrowserPolicyMap.Usb(Mode("on_request", now.AddMinutes(5)), now.AddMinutes(6)));
        Assert.Equal(3, back.Set.Count);
        Assert.Empty(back.Repaired);
        // An org's own GPO already setting one: left alone and reported.
        using (var gpo = _root.CreateSubKey($@"{BrowserPolicyWriter.ChromiumPolicyPath(Browser.Usb)}", true)) gpo.SetValue("Deny_All", 0);
        Assert.Equal(["Deny_All"], BrowserPolicyWriter.ApplyIfUsed(_root, Browser.Usb, BrowserPolicyMap.Usb(Mode("block"), now)).Conflicts);
    }

    [Fact]
    public void Company_drives_only_allows_the_approved_and_never_touches_other_disks()
    {
        const string sandisk = @"USBSTOR\Disk&Ven_SanDisk&Prod_Cruzer&Rev_1.00\4C530001&0";
        Assert.Empty(new BrowserPolicy { UsbMode = "company_drives", UsbApprovedDrives = [sandisk] }.Validate());
        Assert.NotEmpty(new BrowserPolicy { UsbMode = "company_drives", UsbApprovedDrives = [@"SCSI\Disk&Ven_NVMe\5&1e9"] }.Validate());
        Assert.NotEmpty(new BrowserPolicy { UsbApprovedDrives = ["USBSTOR\\x\\y\r\nevil"] }.Validate());
        // Review 3b L2: an ID Windows made up (no serial of its own) stands for no one drive.
        Assert.NotEmpty(new BrowserPolicy { UsbMode = "company_drives",
                                            UsbApprovedDrives = [@"USBSTOR\Disk&Ven_General&Prod_USB_Disk&Rev_2.00\7&1a2b3c&0"] }.Validate());
        Assert.Equal(2, BrowserPolicyMap.Usb(new BrowserPolicy { UsbMode = "company_drives" }, DateTime.UtcNow).Count);   // phones read-only

        // Never used: nothing created.
        Assert.False(BrowserPolicyWriter.ApplyDeviceInstall(_root, null).Changed);
        Assert.Null(_root.OpenSubKey(BrowserPolicyWriter.DeviceInstallPath));

        var r = BrowserPolicyWriter.ApplyDeviceInstall(_root, [sandisk]);
        Assert.Equal(["AllowDenyLayered", "AllowInstanceIDs", "DenyDeviceIDs", "DenyDeviceIDsRetroactive"], r.Set.Order());
        using (var k = _root.OpenSubKey(BrowserPolicyWriter.DeviceInstallPath)!)
        {
            Assert.Equal(1, k.GetValue("AllowDenyLayered"));
            Assert.Equal(1, k.GetValue("DenyDeviceIDsRetroactive"));
            using var deny = k.OpenSubKey("DenyDeviceIDs")!;
            Assert.Equal(@"USB\Class_08", deny.GetValue("1"));                 // USB storage interfaces (UASP too), never SCSI\Disk
            using var allow = k.OpenSubKey("AllowInstanceIDs")!;
            Assert.Equal(sandisk, allow.GetValue("1"));
        }
        Assert.False(BrowserPolicyWriter.ApplyDeviceInstall(_root, [sandisk]).Changed);   // idempotent

        // Someone removed the allow list: put back, reported.
        using (var k = _root.OpenSubKey(BrowserPolicyWriter.DeviceInstallPath, true)!) k.DeleteSubKeyTree("AllowInstanceIDs");
        Assert.NotEmpty(BrowserPolicyWriter.ApplyDeviceInstall(_root, [sandisk]).Repaired);
        // No drive approved yet: every USB disk is held back, and no empty allow list is written.
        BrowserPolicyWriter.ApplyDeviceInstall(_root, []);
        using (var k = _root.OpenSubKey(BrowserPolicyWriter.DeviceInstallPath)!)
            Assert.Null(k.OpenSubKey("AllowInstanceIDs"));

        // Mode off: SAVIO's values go, with the keys they leave empty.
        Assert.NotEmpty(BrowserPolicyWriter.ApplyDeviceInstall(_root, null).Removed);
        Assert.Null(_root.OpenSubKey(@"SOFTWARE\Policies\Microsoft\Windows\DeviceInstall"));

        // An org's own device installation policy: all of it left alone, reported.
        using (var gpo = _root.CreateSubKey(BrowserPolicyWriter.DeviceInstallPath, true)) gpo.SetValue("DenyRemovableDevices", 1);
        var c = BrowserPolicyWriter.ApplyDeviceInstall(_root, [sandisk]);
        Assert.NotEmpty(c.Conflicts);
        Assert.False(c.Changed);
        using (var k = _root.OpenSubKey(BrowserPolicyWriter.DeviceInstallPath)!)
            Assert.Equal(["DenyRemovableDevices"], k.GetValueNames());
    }

    [Fact]
    public void Drives_seen_are_usb_storage_interfaces_including_usb3_uasp_drives()
    {
        // Security review 3b H2: a USB 3 drive using UASP has its disk under SCSI, not USBSTOR, so
        // drives are listed (and approved) by their USB interface, whichever driver serves it.
        void Usb(string id, string service, string? container) {
            using var k = _root.CreateSubKey($@"SYSTEM\CurrentControlSet\Enum\USB\{id}", true);
            k.SetValue("Service", service);
            k.SetValue("DeviceDesc", "@usbstor.inf,%usbstor.devicedesc%;USB Mass Storage Device");
            if (container is not null) k.SetValue("ContainerID", container);
        }
        void Disk(string bus, string id, string name, string container) {
            using var k = _root.CreateSubKey($@"SYSTEM\CurrentControlSet\Enum\{bus}\{id}", true);
            k.SetValue("FriendlyName", name);
            k.SetValue("ContainerID", container);
        }
        Usb(@"VID_0781&PID_5567\4C530001", "USBSTOR", "{c1}");
        Usb(@"VID_04E8&PID_4001\S4UASP01", "UASPStor", "{c2}");
        Usb(@"VID_1234&PID_5678\5&2a3b4c&0&1", "USBSTOR", null);
        Usb(@"VID_046D&PID_C52B\MOUSE1", "HidUsb", null);                                // a mouse: not storage
        // A drive Windows refused a driver (blocked by this very policy) has no Service, only its
        // compatible IDs: it must still be listed, to be approved and reinstalled (live test).
        using (var blocked = _root.CreateSubKey(@"SYSTEM\CurrentControlSet\Enum\USB\VID_23A5&PID_3379\FC2117B8669A0638", true))
        {
            blocked.SetValue("CompatibleIDs", new[] { @"USB\COMPAT_VID_23A5&Class_08", @"USB\Class_08&SubClass_06&Prot_50", @"USB\Class_08" },
                             Microsoft.Win32.RegistryValueKind.MultiString);
            blocked.SetValue("DeviceDesc", "Disk 3.0");
        }
        Disk("USBSTOR", @"Disk&Ven_SanDisk&Prod_Cruzer&Rev_1.00\4C530001&0", "SanDisk Cruzer USB Device", "{c1}");
        Disk("SCSI", @"Disk&Ven_Samsung&Prod_PSSD_T7\7&abc&0&000000", "Samsung PSSD T7 SCSI Disk Device", "{c2}");

        var seen = BrowserPolicyWriter.SeenDrives(_root);
        Assert.Equal(4, seen.Count);
        Assert.Equal("Disk 3.0", seen.Single(s => s.Id == @"USB\VID_23A5&PID_3379\FC2117B8669A0638").Name);
        Assert.Equal("SanDisk Cruzer USB Device", seen.Single(s => s.Id == @"USB\VID_0781&PID_5567\4C530001").Name);
        var uasp = seen.Single(s => s.Id == @"USB\VID_04E8&PID_4001\S4UASP01");
        Assert.Equal("Samsung PSSD T7 SCSI Disk Device", uasp.Name);
        Assert.True(uasp.UniqueSerial);
        var generic = seen.Single(s => s.Id.Contains("5678"));
        Assert.False(generic.UniqueSerial);                                              // Windows made the serial up
        Assert.Equal("USB Mass Storage Device", generic.Name);

        // Every drive with a serial of its own can be approved; a made-up one cannot (review 3b L2).
        Assert.Empty(new BrowserPolicy { UsbApprovedDrives = seen.Where(s => s.UniqueSerial).Select(s => s.Id).ToList() }.Validate());
        Assert.NotEmpty(new BrowserPolicy { UsbApprovedDrives = seen.Where(s => !s.UniqueSerial).Select(s => s.Id).ToList() }.Validate());

        // An approval made before 3b names the disk; it is translated to its USB interface here,
        // and one never seen on this PC is left out.
        var policy = new BrowserPolicy { UsbMode = "company_drives", UsbApprovedDrives =
            [@"USBSTOR\Disk&Ven_SanDisk&Prod_Cruzer&Rev_1.00\4C530001&0", @"USB\VID_04E8&PID_4001\S4UASP01",
             @"USBSTOR\Disk&Ven_Other&Prod_X&Rev_1\NEVERSEEN&0"] };
        Assert.Equal([@"USB\VID_0781&PID_5567\4C530001", @"USB\VID_04E8&PID_4001\S4UASP01"],
                     BrowserPolicyWriter.AllowIds(_root, policy));
    }

    [Fact]
    public void Firefox_is_written_to_only_under_program_files()
    {
        // Review M4: a user-writable install folder is never written to as SYSTEM.
        Assert.False(BrowserPolicyWriter.ProtectedInstall(Path.Combine(_ffDir, "distribution")));
        Assert.False(BrowserPolicyWriter.ProtectedInstall(@"C:\Tools\Firefox\distribution"));
        var pf = Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles);
        Assert.True(BrowserPolicyWriter.ProtectedInstall(Path.Combine(pf, "Mozilla Firefox Test " + Guid.NewGuid().ToString("N"), "distribution")));
        Assert.False(BrowserPolicyWriter.ProtectedInstall(pf + @"\..\Tools\Firefox\distribution"));   // no climbing out
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
