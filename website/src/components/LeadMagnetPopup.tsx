"use client";

import { useEffect, useRef, useState } from "react";
import { usePathname } from "next/navigation";
import { X } from "lucide-react";
import { LeadMagnetForm } from "@/components/LeadMagnetForm";
import { legalNav } from "@/lib/site";
import { needsDecision } from "@/lib/consent";
import { trackEvent } from "@/lib/analytics";

const STORAGE_KEY = "tm-lead-popup";
const QUIET_DAYS = 7;

// Pages where the visitor is already converting, or reading something a popup has no
// business interrupting.
const EXCLUDED = ["/contact", "/pilot", "/resources", ...legalNav.map((l) => l.href)];

/**
 * Offers the offboarding checklist to a visitor who is about to leave without
 * converting — exit intent on desktop, 45 seconds on the page on touch devices (which
 * have no cursor to leave with). Shown at most once a week per browser, and never
 * while the cookie banner is still waiting for an answer: two overlays at once reads
 * as a trap.
 */
export function LeadMagnetPopup() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const closeRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    const path = pathname.replace(/\/$/, "") || "/";
    if (EXCLUDED.some((p) => path === p.replace(/\/$/, "") || path.startsWith(`${p}/`))) return;
    try {
      const last = Number(localStorage.getItem(STORAGE_KEY) || 0);
      if (Date.now() - last < QUIET_DAYS * 86_400_000) return;
    } catch {
      // Storage blocked: we cannot remember a dismissal, so do not ask at all.
      return;
    }

    let armed = false;
    function show() {
      if (needsDecision()) return;
      try {
        localStorage.setItem(STORAGE_KEY, String(Date.now()));
      } catch {}
      setOpen(true);
      trackEvent("lead_popup_shown", { page_path: window.location.pathname });
      cleanup();
    }
    function onMouseOut(e: MouseEvent) {
      if (armed && !e.relatedTarget && e.clientY <= 0) show();
    }

    const touch = window.matchMedia("(hover: none)").matches;
    const timer = window.setTimeout(
      () => (touch ? show() : (armed = true)),
      touch ? 45_000 : 8_000,
    );
    if (!touch) document.addEventListener("mouseout", onMouseOut);

    function cleanup() {
      window.clearTimeout(timer);
      document.removeEventListener("mouseout", onMouseOut);
    }
    return cleanup;
  }, [pathname]);

  useEffect(() => {
    if (!open) return;
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[70] grid place-items-center bg-black/50 p-4 backdrop-blur-sm"
      onClick={(e) => e.target === e.currentTarget && setOpen(false)}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="lead-popup-title"
        className="relative max-h-[calc(100vh-2rem)] w-full max-w-md overflow-y-auto rounded-2xl border border-token bg-surface p-6 shadow-2xl sm:p-7"
      >
        <button
          ref={closeRef}
          onClick={() => setOpen(false)}
          aria-label="Close"
          className="absolute right-3 top-3 rounded-md p-1 text-muted-token hover:text-primary-token"
        >
          <X className="h-5 w-5" />
        </button>
        <p className="text-xs font-semibold uppercase tracking-wider text-brand-500">
          Free checklist
        </p>
        <h2 id="lead-popup-title" className="mt-2 text-xl font-bold tracking-tight">
          Before you go — the Secure Offboarding Checklist
        </h2>
        <p className="mt-2 text-sm text-secondary-token">
          The steps IT teams miss when an employee leaves: accounts, devices, shared
          logins and data. One page, ready to use.
        </p>
        <div className="mt-5">
          <LeadMagnetForm
            assetUrl="/resources/secure-offboarding-checklist.pdf"
            assetName="Secure Offboarding Checklist"
            leadLabel="offboarding_checklist_popup"
          />
        </div>
      </div>
    </div>
  );
}
