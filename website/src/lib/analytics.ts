type AnalyticsParams = Record<string, string | number | boolean | undefined>;

const ATTRIBUTION_KEY = "technomate_first_touch_attribution";

type Attribution = {
  landing_page: string;
  referrer: string;
  utm_source: string;
  utm_medium: string;
  utm_campaign: string;
  utm_content: string;
  utm_term: string;
};

declare global {
  interface Window {
    gtag?: (command: "event", eventName: string, params?: AnalyticsParams) => void;
    fbq?: (command: "track" | "trackCustom", eventName: string, params?: AnalyticsParams) => void;
  }
}

// Map our internal event names to Meta (Facebook) standard events, so a single
// trackEvent() call reports the conversion to GA4 AND the Meta Pixel — which is
// what Google Ads (via GA4 import) and Meta Ads optimize toward.
const META_EVENTS: Record<string, string> = {
  generate_lead: "Lead",
  book_demo_click: "Schedule",
  signup_click: "StartTrial",
};

/**
 * Fire a conversion/interaction event to every ad platform that's live.
 * Safe to call anywhere — it no-ops on the server and when a tag isn't loaded.
 */
export function trackEvent(eventName: string, params?: AnalyticsParams) {
  if (typeof window === "undefined") return;
  window.gtag?.("event", eventName, params);
  const metaEvent = META_EVENTS[eventName];
  if (metaEvent) window.fbq?.("track", metaEvent, params);
}

function currentAttribution(): Attribution {
  const query = new URLSearchParams(window.location.search);
  return {
    landing_page: window.location.href,
    referrer: document.referrer || "direct",
    utm_source: query.get("utm_source") ?? "",
    utm_medium: query.get("utm_medium") ?? "",
    utm_campaign: query.get("utm_campaign") ?? "",
    utm_content: query.get("utm_content") ?? "",
    utm_term: query.get("utm_term") ?? "",
  };
}

/**
 * Capture the first page and campaign for this browser session. This prevents
 * attribution disappearing when someone visits content before converting.
 */
export function captureAttribution(): Attribution | Record<string, never> {
  if (typeof window === "undefined") return {};

  try {
    const existing = window.sessionStorage.getItem(ATTRIBUTION_KEY);
    if (existing) return JSON.parse(existing) as Attribution;

    const attribution = currentAttribution();
    window.sessionStorage.setItem(ATTRIBUTION_KEY, JSON.stringify(attribution));
    return attribution;
  } catch {
    // Storage can be unavailable in strict privacy modes; tracking still works.
    return currentAttribution();
  }
}

/** Return the session's first-touch acquisition context without collecting PII. */
export function getAttribution(): Attribution | Record<string, never> {
  return captureAttribution();
}
