type AnalyticsParams = Record<string, string | number | boolean | undefined>;

declare global {
  interface Window {
    gtag?: (command: "event", eventName: string, params?: AnalyticsParams) => void;
  }
}

/** Send an event only when Google Analytics is available in the browser. */
export function trackEvent(eventName: string, params?: AnalyticsParams) {
  if (typeof window !== "undefined") window.gtag?.("event", eventName, params);
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
