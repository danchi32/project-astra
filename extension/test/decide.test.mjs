// Phase 3 · D3: run with `node --test extension/test/`. No dependencies.
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  decide, downloadOrigin, fromHost, hostOf, isWatched, mergeScans, originFor, readPolicy, toEvent, withOutcome,
  DEFAULT_POLICY, REASONS,
} from "../decide.js";

test("where a download came from, and which upload it is: the host only", () => {
  assert.equal(downloadOrigin({ finalUrl: "https://crm.zoho.com/export?id=7", url: "https://x.in/redirect" }), "crm.zoho.com");
  assert.equal(downloadOrigin({ url: "blob:https://mail.google.com/9b1c" }), "mail.google.com");
  assert.equal(downloadOrigin({ url: "data:text/csv;base64,QQ==", referrer: "https://app.tally.in/report" }), "app.tally.in");
  assert.equal(downloadOrigin({ url: "data:text/csv;base64,QQ==" }), "");

  const downloads = [{ name: "clients.xlsx", size: 100, origin: "old.example.com" },
                     { name: "clients.xlsx", size: 100, origin: "crm.zoho.com" },
                     { name: "notes.txt", size: 5, origin: "drive.google.com" }];
  assert.equal(originFor([{ name: "clients.xlsx", size: 100 }], downloads), "crm.zoho.com");   // the latest
  assert.equal(originFor([{ name: "clients.xlsx", size: 101 }], downloads), null);             // edited since
  assert.equal(originFor([{ name: "photo.jpg", size: 1 }, { name: "notes.txt", size: 5 }], downloads), "drive.google.com");
  assert.equal(originFor([{ name: "a", size: 1 }], [{ name: "a", size: 1, origin: "not a host" }]), null);

  const p = readPolicy({ mode: "warn" });
  const scan = fromHost({ ok: true, counts: { Pan: 3 } });
  assert.equal(toEvent(p, "wetransfer.com", "file", scan, decide(p, scan, "file"), "crm.zoho.com").origin, "crm.zoho.com");
  assert.equal("origin" in toEvent(p, "wetransfer.com", "file", scan, decide(p, scan, "file")), false);
  assert.equal("origin" in toEvent(p, "wetransfer.com", "file", scan, decide(p, scan, "file"), "C:\\Users\\a\\x.xlsx"), false);
});

test("scans of an upload's parts add up, and one unknown part makes the whole unknown", () => {
  const a = fromHost({ ok: true, counts: { Pan: 1 }, keyword_hits: [0] });
  const b = fromHost({ ok: true, counts: { Pan: 2, Aadhaar: 1 }, contact_list: true, keyword_hits: [0, 3] });
  assert.deepEqual(mergeScans(a, b), { ok: true, counts: { Pan: 3, Aadhaar: 1 }, contactList: true,
                                       keywordHits: [0, 3], incomplete: false });
  assert.equal(mergeScans(a, null), null);
  assert.equal(mergeScans(a, { ...b, incomplete: true }), null);
});

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
                        counts: { Pan: 2 }, contact_list: false, keyword_hits: 1, unknown: false,
                        outcome: null, reason: null });

  const nothing = fromHost({ ok: true, counts: {} });
  assert.equal(toEvent(p, "x.in", "paste", nothing, decide(p, nothing)), null);
  assert.equal(toEvent(p, "x.in", "paste", null, decide(p, null)).unknown, true);   // could not check: recorded
  assert.equal(toEvent(p, "", "paste", scan, decide(p, scan)), null);                // no host (file://)
  assert.equal(toEvent(p, "x.in", "print", scan, decide(p, scan)), null);
});

test("justify asks for a reason, but a broken scanner still only warns", () => {
  const p = readPolicy({ mode: "justify" });
  assert.equal(decide(p, found).action, "justify");
  assert.equal(decide(p, clean).action, "allow");
  assert.equal(decide(p, null).action, "warn");
});

test("redact rewrites a paste, a form and text files; anything it cannot rewrite is a warning", () => {
  const p = readPolicy({ mode: "redact" });
  for (const channel of ["paste", "file", "submit"]) assert.equal(decide(p, found, channel).action, "redact");
  assert.equal(decide(p, found, "drop").action, "warn");               // a drop cannot be re-dropped
  // What cannot be rewritten (a PDF, a form's other fields) must be clean, or it is a warning.
  assert.equal(decide(p, found, "file", clean).action, "redact");
  assert.equal(decide(p, found, "file", found).action, "warn");
  assert.equal(decide(p, found, "submit", null).action, "warn");        // the rest could not be checked
  assert.equal(decide(p, clean, "paste").action, "allow");
  assert.equal(decide(p, null, "paste").action, "warn");                // could not check: never "hidden"
  const scan = fromHost({ ok: true, counts: { Pan: 1 } });
  assert.equal(toEvent(p, "chatgpt.com", "paste", scan, decide(p, scan, "paste")).action, "redact");
  assert.equal(withOutcome({ ...toEvent(p, "x.in", "paste", scan, decide(p, scan, "paste")) }, "proceeded", null), null);
});

test("approve holds sensitive content until IT says yes; the prompt can only ask or give up", () => {
  const p = readPolicy({ mode: "approve" });
  assert.equal(decide(p, found, "file").action, "approve");
  assert.equal(decide(p, null, "paste").action, "warn");                 // could not check: a warning, as ever
  const scan = fromHost({ ok: true, counts: { Pan: 1 } });
  const e = toEvent(p, "chatgpt.com", "paste", scan, decide(p, scan));
  assert.equal(withOutcome(e, "requested", null).outcome, "requested");
  assert.equal(withOutcome(e, "cancelled", null).outcome, "cancelled");
  assert.equal(withOutcome(e, "proceeded", null), null);                  // only the host's check lets it through
  assert.equal(withOutcome(e, "requested", "approved"), null);
  assert.equal(withOutcome({ ...e, action: "warn" }, "requested", null), null);
});

test("an answer is recorded only in a shape that fits, with a reason from the list", () => {
  const p = readPolicy({ mode: "justify" });
  const scan = fromHost({ ok: true, counts: { Pan: 1 } });
  const e = toEvent(p, "chatgpt.com", "paste", scan, decide(p, scan));
  assert.equal(e.outcome, null);

  assert.deepEqual(withOutcome(e, "proceeded", "client_request"), { ...e, outcome: "proceeded", reason: "client_request" });
  assert.deepEqual(withOutcome(e, "cancelled", null), { ...e, outcome: "cancelled", reason: null });
  assert.equal(withOutcome(e, "proceeded", null), null);                         // justify needs a reason
  assert.equal(withOutcome(e, "proceeded", "I just felt like it"), null);        // never free text
  assert.equal(withOutcome(e, "cancelled", "approved"), null);
  assert.equal(withOutcome(e, "maybe", null), null);

  const w = { ...e, action: "warn", mode: "warn" };
  assert.equal(withOutcome(w, "proceeded", null).outcome, "proceeded");          // warn takes no reason
  assert.equal(withOutcome(w, "proceeded", "approved"), null);
  assert.equal(withOutcome({ ...e, action: "block" }, "proceeded", null), null); // a block has no answer
  assert.ok(Object.keys(REASONS).every((k) => /^[a-z_]{1,20}$/.test(k)));
});

test("watched sites cover subdomains and nothing else", () => {
  const p = readPolicy({ watchedSites: ["openai.com", "claude.ai"] });
  assert.ok(isWatched(p, "chat.openai.com"));
  assert.ok(isWatched(p, "claude.ai"));
  assert.ok(!isWatched(p, "notopenai.com"));
  assert.ok(!isWatched(p, "openai.com.evil.example"));
  assert.ok(isWatched(readPolicy({}), "anything.example"));   // empty list = every site
});


test("host names compare the same however they are written (security review M4)", () => {
  assert.equal(hostOf("https://ChatGPT.com./c/123"), "chatgpt.com");
  assert.equal(hostOf("chatgpt.com."), "chatgpt.com");
  assert.equal(hostOf("*.openai.com"), "openai.com");
  assert.equal(hostOf("http://bücher.example/"), "xn--bcher-kva.example");
  assert.equal(hostOf("about:blank"), "");
  const p = readPolicy({ watchedSites: ["https://ChatGPT.com/", "*.openai.com", "", 7] });
  assert.deepEqual(p.watchedSites, ["chatgpt.com", "openai.com"]);
  assert.ok(isWatched(p, "chatgpt.com."));                 // trailing dot no longer slips past
  assert.ok(isWatched(p, "chat.openai.com"));
  assert.ok(!isWatched(p, "evilchatgpt.com"));
  const scan = fromHost({ ok: true, counts: { Pan: 1 } });
  assert.equal(toEvent(readPolicy({ mode: "warn" }), "chatgpt.com.", "paste", scan, decide(readPolicy({ mode: "warn" }), scan)).site, "chatgpt.com");
});

test("only known kinds, as whole numbers, come from the host (security review L6)", () => {
  const scan = fromHost({ ok: true, counts: { Pan: 2, "Your account is locked, call IT": 1, Aadhaar: 1.5, Email: -1 } });
  assert.deepEqual(scan.counts, { Pan: 2 });
});
