# Phase 3 · Spike 1 — "Corporate account only" (D2): which services honour an allowed-tenant header, and can our extension set it?

Status: **desk research done (16 Nov 2026); live checks still to run.** They need paid tenant
accounts at each service (see "What it takes to prove it").

## The question
D2 says: on a managed PC, someone can sign in to Google, Microsoft, Dropbox, Slack, ChatGPT
and Claude with the company's account, and not with a personal one. The roadmap plan is for
the SAVIO browser extension (MV3) to add each service's "allowed tenant" request header. The
spike asks two things:

1. Which services honour such a header?
2. Can an MV3 extension set it, or does it only work when a network proxy adds it?

## What each service offers

| Service | Header(s) | Value | Plan needed | Notes |
|---|---|---|---|---|
| Google Workspace | `X-GoogApps-Allowed-Domains` | comma list of the org's domains; `consumer_accounts` keyword allows personal Gmail | Workspace | **No extension needed:** Chrome, Edge and Firefox all have an `AllowedDomainsForApps` browser policy that adds this header to every google.com request. Side effect: delegated mailboxes from domains not in the list stop working. |
| Microsoft 365 / Entra | v1: `Restrict-Access-To-Tenants` + `Restrict-Access-Context`; v2: `sec-Restrict-Tenant-Access-Policy` (`<tenantId>:<policyId>`) | tenant IDs; v2 refers to a cross-tenant policy in Entra | Entra ID P1+ for v2 | **No proxy needed on Windows for Edge:** TRv2 has a Windows device policy (GPO / Intune) that tags traffic from Edge. Microsoft says this does **not** cover Chrome, Firefox or .NET apps. Microsoft calls it temporary, until Universal Tenant Restrictions (Global Secure Access) is generally available. v1 headers must overwrite any value the client already sent. |
| Dropbox | `X-Dropbox-allowed-Team-Ids` | team IDs | **Enterprise only** ("Network control", Admin console → Settings → Security) | Documented as proxy or CASB inserted. One community user's try with a header-modifying extension failed, but their team was not on Enterprise, so it proves nothing either way. **The desktop app pins certificates**, so a TLS-inspecting proxy can't add the header to it. |
| Slack | `X-Slack-Allowed-Workspaces-Requester` (one ID) + `X-Slack-Allowed-Workspaces` (list) | workspace/org IDs | Business+ or Enterprise | Proxy-oriented. Sign-in to a workspace not on the list shows an error. |
| ChatGPT | `ChatGPT-Allowed-Workspace-Id` | workspace UUIDs, comma-separated with no spaces | ChatGPT Enterprise | Logins to workspaces not on the list are filtered out. OpenAI does not clearly document how a *personal* account is treated, so test it. |
| Claude | `anthropic-allowed-org-ids` | org UUIDs; up to 10 header lines and 500 UUIDs, with numbered continuation headers (`;n=K`) beyond that | Claude Enterprise or Console org | Covers web, desktop, API key and OAuth. A duplicate header line gives a 400, so it must **set**, never append. Claude for Government uses a different name and format (`Anthropic-Allowed-Tenant-Ids`, `umb_` IDs). |

## Can the extension set these headers?
- **Mechanically, yes.** `chrome.declarativeNetRequest` `modifyHeaders` with
  `operation: "set"` rewrites request headers before Chrome sends them. The service sees the
  same bytes whether a browser or a proxy added them, because TLS ends at the service. Use
  `set`, never `append`: Claude rejects duplicate lines, and Microsoft v1 expects any client
  value to be overwritten. We have not found a published Chrome list of request headers that
  `set` refuses, so the live test must confirm each of the six names.
- **Only browser traffic is covered.** Desktop apps never pass through the extension: Slack,
  Dropbox, the ChatGPT and Claude desktop apps, Teams and OneDrive. So D2 has two halves:
  1. browser: the extension sets the headers, and for Google and Edge the native browser
     policies do it;
  2. desktop apps: block them, or allow them only where a policy keeps them on the company
     account (Microsoft TRv2 on Windows; OneDrive "allowed tenants"), per D10 (anti-tamper
     and app control).
- **A user can turn off the extension** unless it is force-installed and developer mode and
  incognito are off. That is Spike 2 and D10.

## Proposed D2 design (to confirm with the live test)
1. **Google:** `AllowedDomainsForApps` browser policy, written by the agent for Chrome, Edge
   and Firefox. No extension involvement.
2. **Microsoft:** where the org has Entra P1+, the TRv2 Windows device policy (for Edge) plus
   the extension header for Chrome and Firefox. Otherwise v1 headers from the extension.
3. **Dropbox, Slack, ChatGPT, Claude:** extension `modifyHeaders` `set` rules, built from
   tenant IDs the admin enters per org. These only work on the vendor's enterprise plan,
   so the portal must say so.
4. **Services with no header** (Gemini consumer, Perplexity, personal file-sharing sites):
   block or strict DLP, as the roadmap already says.
5. **Desktop apps of the six:** policy (app control) per org: block, or allow when the
   vendor has a device-level control.

## What it takes to prove it (the live test)
For each service, on a test PC with the extension loaded:
1. With the header set to tenant A, sign in with a tenant-A account: it should succeed.
2. Sign in with a personal or tenant-B account: it should be blocked, with the vendor's
   error.
3. Remove the extension: the personal account should work again. This shows the extension
   is what enforces it.

**Needs from you:**
- test tenants on the required plans: Workspace, M365 with Entra P1, Dropbox Enterprise,
  Slack Business+, ChatGPT Enterprise, Claude Enterprise; or a pilot customer willing to
  test on theirs;
- a test PC or VM where loading an unpacked extension is fine. Not this laptop's everyday
  Chrome.

Until then, **2 of 6 are decided by browser policy alone** (Google; Microsoft for Edge).
The other four rest on documented behaviour plus an untested assumption: that the vendor
honours the header from a browser as it does from a proxy.

## Sources
- Google: https://support.google.com/a/answer/1668854 ·
  https://learn.microsoft.com/en-us/deployedge/microsoft-edge-browser-policies/alloweddomainsforapps ·
  https://firefox-admin-docs.mozilla.org/reference/policies/alloweddomainsforapps/
- Microsoft: https://learn.microsoft.com/entra/identity/enterprise-apps/tenant-restrictions ·
  https://learn.microsoft.com/en-us/entra/external-id/tenant-restrictions-v2 ·
  https://learn.microsoft.com/en-us/entra/external-id/tenant-restrictions-migration
- Dropbox: https://help.dropbox.com/security/network-control ·
  https://www.dropboxforum.com/t5/Integrations/Dropbox-Tenancy-Header-Insertion/m-p/742347
- Slack: https://slack.com/help/articles/360024821873
- ChatGPT: https://help.openai.com/en/articles/20001323-corporate-network-controls-in-chatgpt-enterprise
- Claude: https://support.claude.com/en/articles/13198485-enforce-network-level-access-control-with-tenant-restrictions
- Chrome DNR: https://developer.chrome.com/docs/extensions/reference/api/declarativeNetRequest ·
  https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/API/declarativeNetRequest/ModifyHeaderInfo
