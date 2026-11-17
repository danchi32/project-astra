// Phase 3 · D3: run with `node --test extension/test/`. No dependencies.
import { test } from "node:test";
import assert from "node:assert/strict";
import { decide, isWatched, readPolicy, DEFAULT_POLICY } from "../decide.js";

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

test("watched sites cover subdomains and nothing else", () => {
  const p = readPolicy({ watchedSites: ["openai.com", "claude.ai"] });
  assert.ok(isWatched(p, "chat.openai.com"));
  assert.ok(isWatched(p, "claude.ai"));
  assert.ok(!isWatched(p, "notopenai.com"));
  assert.ok(!isWatched(p, "openai.com.evil.example"));
  assert.ok(isWatched(readPolicy({}), "anything.example"));   // empty list = every site
});
