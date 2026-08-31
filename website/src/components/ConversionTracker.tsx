"use client";

import { useEffect } from "react";
import { site } from "@/lib/site";
import { captureAttribution, getAttribution, trackEvent } from "@/lib/analytics";

/**
 * Tracks high-intent demo and product sign-up clicks with one delegated listener,
 * so new CTAs are covered automatically.
 */
export function ConversionTracker() {
  useEffect(() => {
    captureAttribution();

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
      const context = {
        ...getAttribution(),
        destination: href,
        cta_text: (link.textContent || "").trim().replace(/\s+/g, " ").slice(0, 100),
        page_path: window.location.pathname,
      };
      if (bookingHost && href.includes(bookingHost)) {
        trackEvent("book_demo_click", context);
      } else if (href.startsWith(site.appUrl)) {
        trackEvent("signup_click", context);
      }
    }

    document.addEventListener("click", onClick, { capture: true });
    return () => document.removeEventListener("click", onClick, { capture: true });
  }, []);

  return null;
}
