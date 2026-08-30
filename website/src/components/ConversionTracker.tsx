"use client";

import { useEffect } from "react";
import { site } from "@/lib/site";
import { getAttribution, trackEvent } from "@/lib/analytics";

/**
 * Tracks high-intent demo and product sign-up clicks with one delegated listener,
 * so new CTAs are covered automatically.
 */
export function ConversionTracker() {
  useEffect(() => {
    const bookingHost = (() => {
      try {
        return site.booking ? new URL(site.booking).host : "";
      } catch {
        return "";
      }
    })();
    function onClick(e: MouseEvent) {
      const target = e.target as HTMLElement | null;
      const link = target?.closest?.("a");
      if (!link) return;
      const href = link.getAttribute("href") || "";
      if (bookingHost && href.includes(bookingHost)) {
        trackEvent("book_demo_click", { ...getAttribution(), destination: href });
      } else if (href.startsWith(site.appUrl)) {
        trackEvent("signup_click", { ...getAttribution(), destination: href });
      }
    }

    document.addEventListener("click", onClick, { capture: true });
    return () => document.removeEventListener("click", onClick, { capture: true });
  }, []);

  return null;
}
