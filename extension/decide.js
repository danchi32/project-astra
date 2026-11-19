// Phase 3 · D3: what to do about one paste / drop / upload / form, given the org's policy and
// what the scanner found. A pure module: no browser APIs, so it is tested with `node --test`.
//
// The scanner answers with counts only ({counts:{Aadhaar:1}, contactList, keywordHits,
// incomplete}); nothing here ever sees the text again.

// redact: the sensitive parts are replaced by labels such as [PAN] in a paste, in a form's text
// fields, and in text files chosen for upload. What cannot be rewritten (a drop, a Word or PDF
// file, a form's other fields) must be clean, or it falls back to warn.
// approve: held until IT approves; then the same channel on the same site goes through for a
// while (the host checks the approvals the agent stored for this Windows account).
export const MODES = ["log", "warn", "justify", "redact", "approve", "block"];
export const REDACTABLE = ["paste", "file", "submit"];

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
  // Only the kinds SAVIO knows, as whole numbers: whatever answers on the host's name, its
  // counts cannot put new words on the prompt or in an event (security review L6).
  const counts = {};
  for (const [kind, n] of Object.entries(r.counts && typeof r.counts === "object" ? r.counts : {})) {
    if (Object.hasOwn(LABELS, kind) && Number.isInteger(n) && n > 0) counts[kind] = n;
  }
  return {
    ok: r.ok === true,
    counts,
    contactList: r.contact_list === true,
    keywordHits: Array.isArray(r.keyword_hits) ? r.keyword_hits : [],
    // Text past the scanner's limit was not read: "could not check" too (review H3).
    incomplete: r.incomplete === true || r.truncated === true,
  };
}

const CHANNELS = ["paste", "drop", "file", "submit"];

/**
 * E3: what goes to the agent, in the fixed shape it accepts (AstraAgent.Guard.GuardEvent):
 * a host name, the channel, the mode and the decision, counts and flags. Never the text.
 * Null when there is nothing worth recording: an ordinary paste with nothing found.
 */
export function toEvent(policy, site, channel, scan, result, origin = null) {
  const host = hostOf(site);
  if (!HOST.test(host) || !CHANNELS.includes(channel)) return null;
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
  // C2: where the file came from, as a host name only, and only when known.
  const from = hostOf(origin ?? "");
  if (HOST.test(from)) event.origin = from;
  const notable = event.unknown || event.contact_list || event.keyword_hits > 0 || Object.keys(counts).length > 0;
  return notable ? event : null;
}

const HOST = /^[a-z0-9]([a-z0-9.-]{0,251}[a-z0-9])?$/;
export const MAX_DOWNLOADS = 500;
export const DOWNLOAD_DAYS = 30;

/**
 * C2: the site a download came from: its final URL's host, or for a file a page built itself
 * (blob: or data:) the page it was on. "" when there is none.
 */
export function downloadOrigin(item) {
  const url = String(item?.finalUrl || item?.url || "");
  if (/^(blob|data|filesystem):/i.test(url)) {
    const inner = url.replace(/^blob:/i, "");
    return /^https?:/i.test(inner) ? hostOf(inner) : hostOf(item?.referrer ?? "");
  }
  return hostOf(url);
}

/**
 * C2: the site the first of these files was downloaded from, if the browser saw it downloaded:
 * the most recent download of the same name and size. Only the host ever leaves this module.
 */
export function originFor(files, downloads) {
  for (const f of files ?? []) {
    const hit = [...(downloads ?? [])].reverse().find((d) => d.name === f.name && d.size === f.size);
    if (hit && HOST.test(hit.origin ?? "")) return hit.origin;
  }
  return null;
}

/**
 * A page's host name as SAVIO compares it: lower case, punycode for international names (the
 * URL parser does that), and no trailing dot, so "ChatGPT.com." is "chatgpt.com" (review M4).
 * Accepts a URL or a bare host; "" when there is none.
 */
export function hostOf(value) {
  let s = String(value ?? "").trim();
  if (!s) return "";
  s = s.replace(/^\*\./, "");
  try {
    const url = new URL(/^[a-z][a-z0-9+.-]*:/i.test(s) ? s : "http://" + s);
    return url.hostname.toLowerCase().replace(/\.+$/, "");
  } catch {
    return "";
  }
}

/** Merge what the admin set (chrome.storage.managed) over the defaults, keeping only valid values. */
export function readPolicy(managed) {
  const p = { ...DEFAULT_POLICY };
  if (!managed || typeof managed !== "object") return p;
  if (MODES.includes(managed.mode)) p.mode = managed.mode;
  for (const key of ["watchedSites", "ignoreKinds", "keywords"]) {
    if (Array.isArray(managed[key])) p[key] = managed[key].filter((x) => typeof x === "string").slice(0, 500);
  }
  // A watched entry written as a URL, with a "*." or a trailing dot, still matches (review M4).
  p.watchedSites = [...new Set(p.watchedSites.map(hostOf).filter(Boolean))];
  return p;
}

/** True when this page's host is one the policy watches (a listed host or its subdomain). */
export function isWatched(policy, hostname) {
  if (!policy.watchedSites.length) return true;
  const host = hostOf(hostname);
  return policy.watchedSites.some((s) => host === s || host.endsWith("." + s));
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
export function decide(policy, scan, channel = "paste", fixed = undefined) {
  const unknown = isUnknown(scan);
  const findings = unknown ? [] : sensitiveFindings(policy, scan);
  if (policy.mode === "log") return { action: "allow", findings, unknown };
  if (unknown) return { action: "warn", findings, unknown, reason: "SAVIO could not check this content." };
  if (!findings.length) return { action: "allow", findings, unknown };
  const reason = `This contains ${findings.join(", ")}.`;
  // `fixed`: the scan of what cannot be rewritten (undefined when all of it can). Hiding only
  // some of the sensitive parts would send the rest while saying "hidden": a warning instead.
  const rewritable = REDACTABLE.includes(channel) &&
    (fixed === undefined || (!isUnknown(fixed) && !sensitiveFindings(policy, fixed).length));
  const action = policy.mode === "redact" && !rewritable ? "warn" : policy.mode;
  return { action, findings, unknown, reason };
}

const isUnknown = (scan) => scan === null || scan?.ok === false || scan?.incomplete === true;

/** Two scans of parts of one upload or form, as one. Either one unknown makes it unknown. */
export function mergeScans(a, b) {
  if (isUnknown(a) || isUnknown(b)) return null;
  const counts = { ...a.counts };
  for (const [kind, n] of Object.entries(b.counts ?? {})) counts[kind] = (counts[kind] ?? 0) + n;
  return {
    ok: true, counts,
    contactList: !!(a.contactList || b.contactList),
    keywordHits: [...new Set([...(a.keywordHits ?? []), ...(b.keywordHits ?? [])])],
    incomplete: false,
  };
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
