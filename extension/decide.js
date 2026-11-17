// Phase 3 · D3: what to do about one paste / drop / upload / form, given the org's policy and
// what the scanner found. A pure module: no browser APIs, so it is tested with `node --test`.
//
// The scanner answers with counts only ({counts:{Aadhaar:1}, contactList, keywordHits,
// incomplete}); nothing here ever sees the text again.

export const DEFAULT_POLICY = Object.freeze({
  mode: "log",            // log | warn | block. Pilot default: 14 days of log-only (E8)
  watchedSites: [],       // host names; empty = every site
  ignoreKinds: ["Email"], // e-mail addresses are in every signature; counted, never acted on
  keywords: [],           // admin keywords, matched whole-word by the scanner
});

const LABELS = {
  Aadhaar: "Aadhaar number", Pan: "PAN", Gstin: "GSTIN", PaymentCard: "card number",
  IndianMobile: "mobile number", Email: "e-mail address", BankAccount: "bank account",
};

/** Merge what the admin set (chrome.storage.managed) over the defaults, keeping only valid values. */
export function readPolicy(managed) {
  const p = { ...DEFAULT_POLICY };
  if (!managed || typeof managed !== "object") return p;
  if (["log", "warn", "block"].includes(managed.mode)) p.mode = managed.mode;
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
export function decide(policy, scan) {
  const unknown = scan === null || scan?.ok === false || scan?.incomplete === true;
  const findings = unknown ? [] : sensitiveFindings(policy, scan);
  if (policy.mode === "log") return { action: "allow", findings, unknown };
  if (unknown) return { action: "warn", findings, unknown, reason: "SAVIO could not check this content." };
  if (!findings.length) return { action: "allow", findings, unknown };
  const reason = `This contains ${findings.join(", ")}.`;
  return { action: policy.mode === "block" ? "block" : "warn", findings, unknown, reason };
}
