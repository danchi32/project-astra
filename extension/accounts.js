// Phase 3 · D2 beyond Google: sign-in to the organization's own accounts only.
//
// Microsoft 365, Claude, ChatGPT and Slack each enforce this themselves when a request carries
// their header naming the org's tenant / organizations / workspaces. Usually a TLS-inspecting
// proxy adds it; here the extension does, on that service's sign-in domains only. Checked live
// (18 Nov): the headers reach the server, and Microsoft's sign-in reads its header at once.
//
// The IDs come from managed policy (written by the SAVIO agent). Anything not shaped like an ID
// is dropped here as well: these become request headers.

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const SLACK = /^[TE][A-Z0-9]{6,20}$/;
const MAX_IDS = 50;
const TYPES = ["main_frame", "sub_frame", "xmlhttprequest", "websocket", "other"];
export const FIRST_RULE_ID = 1000;

const ids = (v, shape) =>
  Array.isArray(v) && v.length > 0 && v.length <= MAX_IDS && v.every((x) => typeof x === "string" && shape.test(x));

/** The dynamic rules for these managed settings: none when nothing is set. */
export function accountRules(managed) {
  const m = managed && typeof managed === "object" ? managed : {};
  const rules = [];
  const add = (requestDomains, headers) => rules.push({
    id: FIRST_RULE_ID + rules.length, priority: 1,
    // "set" replaces whatever the page or another hop sent, as a proxy must.
    action: { type: "modifyHeaders", requestHeaders: headers.map(([header, value]) => ({ header, operation: "set", value })) },
    condition: { requestDomains, resourceTypes: TYPES },
  });

  const [tenant, policy, ...extra] = typeof m.microsoftTenant === "string" ? m.microsoftTenant.split(":") : [];
  if (UUID.test(tenant ?? "") && UUID.test(policy ?? "") && extra.length === 0)
    // Tenant restrictions v2. login.live.com too, so personal Microsoft accounts follow the policy.
    add(["login.microsoftonline.com", "login.microsoft.com", "login.windows.net", "login.live.com"],
        [["sec-Restrict-Tenant-Access-Policy", `${tenant}:${policy}`]]);
  if (ids(m.claudeOrgs, UUID))
    add(["claude.ai", "claude.com", "anthropic.com"], [["anthropic-allowed-org-ids", m.claudeOrgs.join(",")]]);
  if (ids(m.chatgptWorkspaces, UUID))
    add(["chatgpt.com", "chat.openai.com"], [["ChatGPT-Allowed-Workspace-Id", m.chatgptWorkspaces.join(",")]]);
  if (typeof m.slackRequester === "string" && SLACK.test(m.slackRequester) && ids(m.slackAllowed, SLACK))
    add(["slack.com"], [["X-Slack-Allowed-Workspaces-Requester", m.slackRequester],
                        ["X-Slack-Allowed-Workspaces", m.slackAllowed.join(",")]]);
  return rules;
}
