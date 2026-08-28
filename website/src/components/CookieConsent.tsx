"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Cookie } from "lucide-react";
import {
  REQUIRE_PRIOR_CONSENT,
  needsDecision,
  setConsent,
} from "@/lib/consent";

/**
 * Cookie banner.
 *
 * Renders nothing on the server and nothing until mounted, so the static HTML is
 * identical for every visitor and hydration cannot mismatch. What the visitor is told
 * depends on the posture (see lib/consent.ts): in Europe nothing has run yet and the
 * banner says so; elsewhere analytics is already running and the banner offers to stop
 * it.
 */
export function CookieConsent() {
  const [open, setOpen] = useState(false);
  const [priorConsent, setPriorConsent] = useState(false);

  useEffect(() => {
    setPriorConsent(REQUIRE_PRIOR_CONSENT());
    setOpen(needsDecision());
  }, []);

  if (!open) return null;

  function choose(value: "granted" | "denied") {
    setConsent(value);
    setOpen(false);
  }

  return (
    <div
      role="dialog"
      aria-label="Cookie preferences"
      className="fixed inset-x-0 bottom-0 z-[60] p-3 sm:p-4"
    >
      <div className="mx-auto flex max-w-4xl flex-col gap-4 rounded-2xl border border-token bg-surface p-5 shadow-lg sm:flex-row sm:items-center">
        <Cookie className="hidden h-6 w-6 shrink-0 text-brand-500 sm:block" />
        <p className="flex-1 text-sm leading-relaxed text-secondary-token">
          {priorConsent
            ? "We use analytics and advertising cookies to understand how this site is used. They stay switched off until you allow them."
            : "We use analytics and advertising cookies to understand how this site is used. You can turn them off at any time."}{" "}
          <Link href="/cookies/" className="text-brand-500 hover:underline">
            Cookie Policy
          </Link>
        </p>
        <div className="flex shrink-0 gap-2">
          <button
            type="button"
            onClick={() => choose("denied")}
            className="rounded-lg border border-token px-4 py-2 text-sm font-medium text-secondary-token hover:text-brand-500"
          >
            Decline
          </button>
          <button
            type="button"
            onClick={() => choose("granted")}
            className="rounded-lg px-4 py-2 text-sm font-semibold text-white"
            style={{ background: "var(--accent)" }}
          >
            Accept
          </button>
        </div>
      </div>
    </div>
  );
}
