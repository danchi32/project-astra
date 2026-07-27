type AnalyticsParams = Record<string, string | number | boolean | undefined>;

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

/** Preserve acquisition context with a lead, even after it leaves analytics. */
export function getAttribution() {
  if (typeof window === "undefined") return {};

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
