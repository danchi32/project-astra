"use client";

import { useEffect } from "react";
import { site } from "@/lib/site";
import { getAttribution, trackEvent } from "@/lib/analytics";

/**
 * Fires a `book_demo_click` conversion whenever a visitor clicks a link to the
 * booking page (Cal.com). Uses one delegated listener instead of wiring every
 * "Book a demo" button, so new CTAs are covered automatically.
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
    if (!bookingHost) return;

    function onClick(e: MouseEvent) {
      const target = e.target as HTMLElement | null;
      const link = target?.closest?.("a");
      if (!link) return;
      const href = link.getAttribute("href") || "";
      if (href.includes(bookingHost)) {
        trackEvent("book_demo_click", { ...getAttribution(), destination: href });
      }
    }

    document.addEventListener("click", onClick, { capture: true });
    return () => document.removeEventListener("click", onClick, { capture: true });
  }, []);

  return null;
}
