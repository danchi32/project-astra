import { test } from "node:test";
import assert from "node:assert/strict";
import { FIRST_RULE_ID, accountRules } from "../accounts.js";

const T = "aaaabbbb-0000-cccc-1111-dddd2222eeee";
const P = "1aaaaaa1-2bb2-3cc3-4dd4-5eeeeeeeeee5";
const header = (rule) => Object.fromEntries(rule.action.requestHeaders.map((h) => [h.header, h.value]));

test("nothing set, no rules", () => {
  assert.deepEqual(accountRules(null), []);
  assert.deepEqual(accountRules({ mode: "warn" }), []);
});

test("each service gets its own header on its own sign-in domains, set not appended", () => {
  const rules = accountRules({
    microsoftTenant: `${T}:${P}`, claudeOrgs: [T], chatgptWorkspaces: [T, P],
    slackRequester: "E0123ABCD", slackAllowed: ["E0123ABCD", "T0456EFGH"],
  });
  assert.equal(rules.length, 4);
  assert.deepEqual(rules.map((r) => r.id), [0, 1, 2, 3].map((i) => FIRST_RULE_ID + i));
  assert.ok(rules.every((r) => r.action.requestHeaders.every((h) => h.operation === "set")));
  assert.equal(header(rules[0])["sec-Restrict-Tenant-Access-Policy"], `${T}:${P}`);
  assert.ok(rules[0].condition.requestDomains.includes("login.live.com"));
  assert.equal(header(rules[1])["anthropic-allowed-org-ids"], T);
  assert.equal(header(rules[2])["ChatGPT-Allowed-Workspace-Id"], `${T},${P}`);
  assert.deepEqual(header(rules[3]), { "X-Slack-Allowed-Workspaces-Requester": "E0123ABCD",
                                       "X-Slack-Allowed-Workspaces": "E0123ABCD,T0456EFGH" });
  assert.ok(rules[0].condition.resourceTypes.includes("main_frame"));
});

test("anything not shaped like an ID is dropped: these become headers", () => {
  assert.deepEqual(accountRules({ microsoftTenant: `${T}:${P}:extra` }), []);
  assert.deepEqual(accountRules({ microsoftTenant: T }), []);
  assert.deepEqual(accountRules({ claudeOrgs: [`${T}\r\nX-Evil: 1`] }), []);
  assert.deepEqual(accountRules({ chatgptWorkspaces: "not a list" }), []);
  assert.deepEqual(accountRules({ chatgptWorkspaces: Array(51).fill(T) }), []);
  assert.deepEqual(accountRules({ slackRequester: "E0123ABCD", slackAllowed: [] }), []);
  assert.deepEqual(accountRules({ slackRequester: "E0123ABCD,T1", slackAllowed: ["E0123ABCD"] }), []);
});

test("an ID pasted in capitals is the same ID, sent in lowercase (review L1)", () => {
  const rules = accountRules({ microsoftTenant: `${T.toUpperCase()}:${P}`, claudeOrgs: [T.toUpperCase()] });
  assert.equal(rules.length, 2);
  assert.equal(header(rules[0])["sec-Restrict-Tenant-Access-Policy"], `${T}:${P}`);
  assert.equal(header(rules[1])["anthropic-allowed-org-ids"], T);
});
