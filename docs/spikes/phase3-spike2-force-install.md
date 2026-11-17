# Phase 3 · Spike 2 — Force-installing the SAVIO extension on PCs not joined to a domain

Status: **desk research done (16 Nov 2026); live test still to run** (on a VM, plan below).

## The question
Our customers' PCs are mostly not domain-joined. This laptop is a typical one: `WORKGROUP`,
and not Entra-, domain- or workplace-joined (`dsregcmd /status`). Can the agent, running as
LocalSystem, force-install the extension and lock the browser down on such PCs?
- force-install through `ExtensionInstallForcelist`;
- incognito off;
- extension developer mode off;
- URL blocking.

## What the vendors document
| Browser | Force-install on a non-domain Windows PC | Notes |
|---|---|---|
| **Chrome** | **Only extensions listed in the Chrome Web Store.** Off-store (self-hosted CRX) force-install needs the PC to be Active Directory-joined, Entra-joined, or enrolled in a management system. | Policy key `HKLM\SOFTWARE\Policies\Google\Chrome\ExtensionInstallForcelist`; values `1`, `2`, … = `<id>;https://clients2.google.com/service/update2/crx`. Non-domain Chrome also ignores Group Policy as such: use the registry keys directly, as Google recommends. Third-party testing (PolicyPak) found some policies apply on workgroup PCs and others don't, so every policy we depend on must be tested. |
| **Edge** | **Only extensions listed on the Edge Add-ons site.** Same rule as Chrome. | `HKLM\SOFTWARE\Policies\Microsoft\Edge\ExtensionInstallForcelist`. Some Edge policies are documented as "AD-joined or Pro/Enterprise MDM-enrolled only". |
| **Firefox** | **Works.** `distribution\policies.json` in the install folder is read on any Windows PC. | `ExtensionSettings` → `{ "<id>": { "installation_mode": "force_installed", "install_url": "https://…/savio.xpi" } }`. The XPI must be **signed by Mozilla**: an "unlisted" AMO submission gets signed and can be self-hosted. |

**Lock-down policies we need (D10):**
- `ExtensionDeveloperModeSettings = 1` (Disallow), in Chrome and Edge 128+.
- `DeveloperToolsAvailability`. It also controls developer mode when the setting above is
  unset.
- `IncognitoModeAvailability = 1` / Edge `InPrivateModeAvailability = 1`. Firefox:
  `DisablePrivateBrowsing`.
- `URLBlocklist` / `URLAllowlist`. Firefox: `WebsiteFilter`.
- `BrowserSignin` / `BrowserAddPersonEnabled = false`, so a second profile can't escape the
  policy. Profiles apply machine policies, but an unmanaged *browser* can still be
  installed. That part belongs to D10 app control.

Whether each of these is honoured on a workgroup PC is **not** settled by the docs. It is
the main thing the live test must answer.

## What this means for the design
1. **Publish the extension to both stores.** Use the Chrome Web Store with **unlisted**
   visibility, and Edge Add-ons. Self-hosting would only work on domain-joined PCs, which
   our customers mostly don't have. Store review takes days and every update goes through
   it again, so plan releases around that.
   - **Open question:** does an *unlisted* Web Store item count as "listed in the Chrome Web
     Store" for force-install? The sources don't say. If it doesn't, the listing has to be
     public, with a description that makes clear it is for organizations using SAVIO.
2. **Firefox:** sign the extension through AMO "unlisted", host the XPI ourselves, and have
   the agent write `policies.json`.
3. **The agent writes the policies**: the HKLM registry for Chrome and Edge, and the file
   for Firefox. It re-checks them on every inventory cycle. A user who is a **local admin**
   (common at small firms) can delete the keys. The agent restores them and reports
   "browser policy tampered" (an N1 alert). We cannot stop a local admin, only notice and
   repair.
4. **Fallback when force-install is ignored:** Chrome Enterprise Core (free, cloud
   management through an enrollment token in the registry) makes Chrome a managed browser
   that reliably applies all cloud policies. It needs a Google Admin account per org, or
   one of ours, and we have not verified whether it lifts the off-store restriction. Keep
   it in reserve and decide after the test.
5. **Unsupported browsers** (Brave, Opera, Vivaldi, portable builds): D10 app control
   blocks or uninstalls them per policy, as the roadmap already says. Brave is Chromium and
   reads `HKLM\SOFTWARE\Policies\BraveSoftware\Brave`, so it could be supported later.

## Live test plan (needs a Windows 11 VM in WORKGROUP; not this laptop's everyday browsers)
This laptop already carries a `LocalNetworkAccessAllowedForUrls` policy from another tool.
Changing its browsers' policies would affect daily use, so the test runs on a VM.

1. **Force-install from the store:** add a well-known public Web Store extension to the
   forcelist through HKLM, then restart Chrome. Check that it installed and can't be
   removed. Repeat in Edge with an Add-ons item.
2. **Unlisted item:** once our extension is uploaded to the store as unlisted (needs the
   developer account), repeat step 1 with its ID. This answers the open question.
3. **Each lock-down policy:** set it, and confirm in `chrome://policy` / `edge://policy`
   that it shows "OK" with no "ignored on unmanaged" warning, and that the setting
   actually behaves.
4. **Firefox:** `policies.json` with a signed XPI. Confirm it installs, and that
   `about:policies` shows the policies active.
5. **Tamper:** delete the keys as a local admin, and see how long until the agent restores
   them.

**Needs from you:**
- a Chrome Web Store developer account and an Edge Partner Center account (already on
  the founder checklist);
- a Mozilla AMO account;
- a Windows 11 VM (Hyper-V on this laptop works) or a spare PC.

## Sources
- Chrome extension policies (Windows): https://support.google.com/chrome/a/answer/7532015
- Chrome registry policies: https://support.google.com/chrome/a/answer/9131254
- Chrome Enterprise Core: https://support.google.com/chrome/a/answer/9301891
- Edge forcelist: https://learn.microsoft.com/en-us/deployedge/microsoft-edge-browser-policies/extensioninstallforcelist
- Edge developer mode: https://learn.microsoft.com/en-us/deployedge/microsoft-edge-browser-policies/extensiondevelopermodesettings
- Edge store-only Q&A: https://learn.microsoft.com/en-us/answers/questions/2379289/why-is-edge-extension-force-install-policy-restric
- Chromium forum (forcelist "not listed" warning): https://groups.google.com/a/chromium.org/g/chromium-extensions/c/wp4A-6NC2QY
- PolicyPak on workgroup Chrome: https://kb.policypak.com/kb/article/284-02-which-items-in-chrome-will-and-will-not-work-when-non-domain-joined/
- Firefox policies.json deployment: https://support.pendo.io/hc/en-us/articles/21165410719771
