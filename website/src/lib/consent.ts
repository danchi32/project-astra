/**
 * Cookie-consent state for the marketing site.
 *
 * This is a static export — there is no server to geolocate a request — so the posture
 * is decided in the browser from the visitor's time zone. That is deliberately coarse
 * and deliberately over-inclusive: treating a non-European visitor as European costs a
 * little analytics data, while the reverse costs compliance.
 *
 * Two postures:
 *
 *   opt-in   Nothing non-essential runs until the visitor accepts. Applied to Europe,
 *            where prior consent is the rule.
 *   opt-out  Analytics runs, the banner is still shown, and the visitor can withdraw.
 *
 * If counsel decides one posture should apply worldwide, change REQUIRE_PRIOR_CONSENT
 * to `() => true` (or `() => false`) — nothing else needs to move.
 */

export type ConsentValue = "granted" | "denied";

const STORAGE_KEY = "tm-consent";
const EVENT = "tm-consent-change";

/**
 * True when the visitor is somewhere prior consent is required. Any `Europe/*` zone
 * counts, plus the Atlantic zones belonging to European states. Over-inclusive on
 * purpose — Turkey and Russia are swept in, and that is the safe direction to err.
 */
function requiresPriorConsent(): boolean {
  try {
    const tz = Intl.DateTimeFormat().resolvedOptions().timeZone || "";
    return (
      tz.startsWith("Europe/") ||
      ["Atlantic/Reykjavik", "Atlantic/Canary", "Atlantic/Madeira", "Atlantic/Azores", "Atlantic/Faroe"].includes(tz)
    );
  } catch {
    // A browser that will not tell us the zone gets the stricter treatment.
    return true;
  }
}

export const REQUIRE_PRIOR_CONSENT = requiresPriorConsent;

/** What the visitor chose, or null if they have not chosen yet. */
export function storedConsent(): ConsentValue | null {
  try {
    const v = localStorage.getItem(STORAGE_KEY);
    return v === "granted" || v === "denied" ? v : null;
  } catch {
    // Private mode, blocked storage — behave as if nothing was chosen.
    return null;
  }
}

/**
 * The consent state to apply right now.
 *
 * Before a choice is made this is "denied" in Europe and "granted" elsewhere; after a
 * choice it is whatever the visitor picked, everywhere.
 */
export function effectiveConsent(): ConsentValue {
  const stored = storedConsent();
  if (stored) return stored;
  return requiresPriorConsent() ? "denied" : "granted";
}

/** True when the banner still needs an answer. */
export function needsDecision(): boolean {
  return storedConsent() === null;
}

/** Record a choice and tell everything listening. */
export function setConsent(value: ConsentValue): void {
  try {
    localStorage.setItem(STORAGE_KEY, value);
  } catch {
    // Storage refused. The choice still applies to this page view via the event below.
  }
  window.dispatchEvent(new CustomEvent<ConsentValue>(EVENT, { detail: value }));
}

/** Subscribe to consent changes. Returns an unsubscribe function. */
export function onConsentChange(fn: (v: ConsentValue) => void): () => void {
  const handler = (e: Event) => fn((e as CustomEvent<ConsentValue>).detail);
  window.addEventListener(EVENT, handler);
  return () => window.removeEventListener(EVENT, handler);
}
