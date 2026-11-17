// Phase 3 · D3: run with `node --test extension/test/`. No dependencies.
import { test } from "node:test";
import assert from "node:assert/strict";
import { decide, fromHost, isWatched, readPolicy, toEvent, DEFAULT_POLICY } from "../decide.js";

const found = { ok: true, counts: { Aadhaar: 1, Email: 3 }, contactList: false, keywordHits: [] };
const clean = { ok: true, counts: { Email: 2 }, contactList: false, keywordHits: [] };

test("log mode never holds anything up, but still reports what it saw", () => {
  const r = decide(readPolicy({ mode: "log" }), found);
  assert.equal(r.action, "allow");
  assert.deepEqual(r.findings, ["1 Aadhaar number"]);
});

test("warn and block act only on what the policy cares about", () => {
  assert.equal(decide(readPolicy({ mode: "warn" }), found).action, "warn");
  assert.equal(decide(readPolicy({ mode: "block" }), found).action, "block");
  assert.equal(decide(readPolicy({ mode: "block" }), clean).action, "allow");   // e-mails ignored by default
  assert.equal(decide(readPolicy({ mode: "block", ignoreKinds: [] }), clean).action, "block");
});

test("a contact list or a keyword counts as sensitive", () => {
  const p = readPolicy({ mode: "block" });
  assert.equal(decide(p, { ok: true, counts: {}, contactList: true }).action, "block");
  assert.equal(decide(p, { ok: true, counts: {}, keywordHits: [0] }).action, "block");
});

test("an unreachable or timed-out scanner is never 'clean', and never a hard block", () => {
  for (const scan of [null, { ok: false }, { ok: true, counts: {}, incomplete: true }]) {
    assert.equal(decide(readPolicy({ mode: "block" }), scan).action, "warn");
    assert.equal(decide(readPolicy({ mode: "log" }), scan).action, "allow");
  }
});

test("the policy is read defensively", () => {
  assert.deepEqual(readPolicy(undefined), { ...DEFAULT_POLICY });
  const p = readPolicy({ mode: "delete-everything", watchedSites: ["chatgpt.com", 42, null], keywords: "nope" });
  assert.equal(p.mode, "log");
  assert.deepEqual(p.watchedSites, ["chatgpt.com"]);
  assert.deepEqual(p.keywords, []);
});

test("the host's snake_case answer is read, so contact lists and keywords count", () => {
  const scan = fromHost({ ok: true, counts: { Pan: 1 }, contact_list: true, keyword_hits: [0, 2] });
  assert.equal(scan.contactList, true);
  assert.deepEqual(scan.keywordHits, [0, 2]);
  const p = readPolicy({ mode: "block" });
  assert.equal(decide(p, fromHost({ ok: true, counts: {}, keyword_hits: [1] })).action, "block");
  assert.equal(fromHost(undefined), null);
});

test("an event carries counts and flags, never text, and only when something was found", () => {
  const p = readPolicy({ mode: "warn" });
  const scan = fromHost({ ok: true, counts: { Pan: 2, Email: 0 }, keyword_hits: [3] });
  const e = toEvent(p, "Chat.OpenAI.com", "paste", scan, decide(p, scan));
  assert.deepEqual(e, { site: "chat.openai.com", channel: "paste", mode: "warn", action: "warn",
                        counts: { Pan: 2 }, contact_list: false, keyword_hits: 1, unknown: false });

  const nothing = fromHost({ ok: true, counts: {} });
  assert.equal(toEvent(p, "x.in", "paste", nothing, decide(p, nothing)), null);
  assert.equal(toEvent(p, "x.in", "paste", null, decide(p, null)).unknown, true);   // could not check: recorded
  assert.equal(toEvent(p, "", "paste", scan, decide(p, scan)), null);                // no host (file://)
  assert.equal(toEvent(p, "x.in", "print", scan, decide(p, scan)), null);
});

test("watched sites cover subdomains and nothing else", () => {
  const p = readPolicy({ watchedSites: ["openai.com", "claude.ai"] });
  assert.ok(isWatched(p, "chat.openai.com"));
  assert.ok(isWatched(p, "claude.ai"));
  assert.ok(!isWatched(p, "notopenai.com"));
  assert.ok(!isWatched(p, "openai.com.evil.example"));
  assert.ok(isWatched(readPolicy({}), "anything.example"));   // empty list = every site
});
