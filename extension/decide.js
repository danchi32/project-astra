// Phase 3 · D3: what to do about one paste / drop / upload / form, given the org's policy and
// what the scanner found. A pure module: no browser APIs, so it is tested with `node --test`.
//
// The scanner answers with counts only ({counts:{Aadhaar:1}, contactList, keywordHits,
// incomplete}); nothing here ever sees the text again.

// redact: a paste goes in with the sensitive parts replaced by labels such as [PAN]. Only a
// paste can be rewritten; a file, a drop or a form falls back to warn.
// approve: held until IT approves; then the same channel on the same site goes through for a
// while (the host checks the approvals the agent stored for this Windows account).
export const MODES = ["log", "warn", "justify", "redact", "approve", "block"];
export const REDACTABLE = ["paste"];

// D7: why someone went ahead after a "justify" prompt. A fixed list, never typed text: the
// event schema has no free-text field (E4), and that promise does not bend for this.
export const REASONS = Object.freeze({
  client_request: "The client asked for it",
  approved: "My manager approved it",
  not_real: "It is test or sample data",
  own_data: "It is my own information",
  other: "Another work reason",
});

export const DEFAULT_POLICY = Object.freeze({
  mode: "log",            // log | warn | justify | redact | block. Pilot default: 14 days of log-only (E8)
  watchedSites: [],       // host names; empty = every site
  ignoreKinds: ["Email"], // e-mail addresses are in every signature; counted, never acted on
  keywords: [],           // admin keywords, matched whole-word by the scanner
});

const LABELS = {
  Aadhaar: "Aadhaar number", Pan: "PAN", Gstin: "GSTIN", PaymentCard: "card number",
  IndianMobile: "mobile number", Email: "e-mail address", BankAccount: "bank account",
};

/** The host answers in snake_case (contact_list, keyword_hits); everything here reads this shape. */
export function fromHost(r) {
  if (!r || typeof r !== "object") return null;
  return {
    ok: r.ok === true,
    counts: r.counts && typeof r.counts === "object" ? r.counts : {},
    contactList: r.contact_list === true,
    keywordHits: Array.isArray(r.keyword_hits) ? r.keyword_hits : [],
    incomplete: r.incomplete === true,
  };
}

const CHANNELS = ["paste", "drop", "file", "submit"];

/**
 * E3: what goes to the agent, in the fixed shape it accepts (AstraAgent.Guard.GuardEvent):
 * a host name, the channel, the mode and the decision, counts and flags. Never the text.
 * Null when there is nothing worth recording: an ordinary paste with nothing found.
 */
export function toEvent(policy, site, channel, scan, result) {
  const host = String(site || "").toLowerCase();
  if (!/^[a-z0-9]([a-z0-9.-]{0,251}[a-z0-9])?$/.test(host) || !CHANNELS.includes(channel)) return null;
  const counts = {};
  for (const [kind, n] of Object.entries(scan?.counts ?? {})) if (Number.isInteger(n) && n > 0) counts[kind] = n;
  const event = {
    site: host, channel, mode: policy.mode, action: result.action, counts,
    contact_list: !result.unknown && !!scan?.contactList,
    keyword_hits: result.unknown ? 0 : Math.min(scan?.keywordHits?.length ?? 0, 200),
    unknown: !!result.unknown,
    outcome: null,   // D7: "proceeded" / "cancelled" once a warn or justify prompt is answered
    reason: null,
  };
  const notable = event.unknown || event.contact_list || event.keyword_hits > 0 || Object.keys(counts).length > 0;
  return notable ? event : null;
}

/** Merge what the admin set (chrome.storage.managed) over the defaults, keeping only valid values. */
export function readPolicy(managed) {
  const p = { ...DEFAULT_POLICY };
  if (!managed || typeof managed !== "object") return p;
  if (MODES.includes(managed.mode)) p.mode = managed.mode;
  for (const key of ["watchedSites", "ignoreKinds", "keywords"]) {
    if (Array.isArray(managed[key])) p[key] = managed[key].filter((x) => typeof x === "string").slice(0, 500);
  }
  return p;
}

/** True when this page's host is one the policy watches (a listed host or its subdomain). */
export function isWatched(policy, hostname) {
  if (!policy.watchedSites.length) return true;
  const host = String(hostname || "").toLowerCase();
  return policy.watchedSites.some((s) => host === s.toLowerCase() || host.endsWith("." + s.toLowerCase()));
}

/** What was found that the policy cares about, as human words. */
export function sensitiveFindings(policy, scan) {
  const found = [];
  for (const [kind, n] of Object.entries(scan?.counts ?? {})) {
    if (n > 0 && !policy.ignoreKinds.includes(kind)) found.push(`${n} ${LABELS[kind] ?? kind}${n > 1 ? "s" : ""}`);
  }
  if (scan?.contactList) found.push("a contact list");
  if (scan?.keywordHits?.length) found.push("a restricted keyword");
  return found;
}

/**
 * The decision. `scan` is null when the scanner could not be reached; `scan.incomplete` when
 * it timed out. Neither is ever treated as "clean" in warn or block mode, and neither blocks
 * outright: a broken scanner must not stop a whole office pasting, so it warns instead and the
 * warning is logged.
 */
export function decide(policy, scan, channel = "paste") {
  const unknown = scan === null || scan?.ok === false || scan?.incomplete === true;
  const findings = unknown ? [] : sensitiveFindings(policy, scan);
  if (policy.mode === "log") return { action: "allow", findings, unknown };
  if (unknown) return { action: "warn", findings, unknown, reason: "SAVIO could not check this content." };
  if (!findings.length) return { action: "allow", findings, unknown };
  const reason = `This contains ${findings.join(", ")}.`;
  const action = policy.mode === "redact" && !REDACTABLE.includes(channel) ? "warn" : policy.mode;
  return { action, findings, unknown, reason };
}

/**
 * D7: the event once the person has answered a warn or justify prompt. Null if the answer
 * does not fit: a reason only for "went ahead" after "justify", and only from REASONS.
 */
export function withOutcome(event, outcome, reason) {
  if (event?.action === "approve") {
    // From the prompt: asked IT, or gave up. "proceeded" comes only from the host's check.
    return ["requested", "cancelled"].includes(outcome) && reason == null ? { ...event, outcome, reason: null } : null;
  }
  if (!event || !["warn", "justify"].includes(event.action)) return null;
  if (!["proceeded", "cancelled"].includes(outcome)) return null;
  const needsReason = event.action === "justify" && outcome === "proceeded";
  if (needsReason !== Object.hasOwn(REASONS, reason ?? "")) return null;
  return { ...event, outcome, reason: needsReason ? reason : null };
}
