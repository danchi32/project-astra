"use client";

import { useEffect, useState } from "react";
import { ArrowRight, X } from "lucide-react";
import { bookDemo } from "@/lib/site";

/**
 * A slim bar pinned to the top of a blog post once the reader is past the intro. Top,
 * not bottom: the bottom corners belong to WhatsApp and the site assistant, and the
 * cookie banner takes the bottom edge — a fourth thing down there would cover text.
 * The navbar scrolls away with the page, so the top edge is free.
 *
 * Dismissal lasts for the page view only; the next article asks again.
 */
export function BlogStickyCta() {
  const [visible, setVisible] = useState(false);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    const onScroll = () => setVisible(window.scrollY > 700);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  if (dismissed) return null;

  return (
    <div
      className={`fixed inset-x-0 top-0 z-40 border-b border-token bg-surface/95 shadow-lg backdrop-blur transition-transform duration-300 ${
        visible ? "translate-y-0" : "-translate-y-full"
      }`}
      aria-hidden={!visible}
    >
      <div className="mx-auto flex max-w-5xl items-center gap-3 px-4 py-2.5">
        <p className="min-w-0 flex-1 text-sm text-primary-token">
          <span className="font-semibold">Managing 50–500 Windows PCs?</span>{" "}
          <span className="hidden text-secondary-token sm:inline">
            Book a 30-minute fleet assessment — recurring tickets, patch gaps and where
            automation is safe.
          </span>
        </p>
        <a
          href={bookDemo.href}
          {...(bookDemo.external ? { target: "_blank", rel: "noopener" } : {})}
          tabIndex={visible ? 0 : -1}
          className="inline-flex shrink-0 items-center gap-1.5 rounded-lg bg-brand-600 px-3.5 py-2 text-sm font-semibold text-white transition hover:bg-brand-500"
        >
          Book assessment <ArrowRight className="h-4 w-4" />
        </a>
        <button
          onClick={() => setDismissed(true)}
          aria-label="Dismiss"
          tabIndex={visible ? 0 : -1}
          className="shrink-0 rounded-md p-1 text-muted-token hover:text-primary-token"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
