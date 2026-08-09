"use client";

import { useEffect, useState } from "react";
import { site } from "@/lib/site";
import { cn } from "@/lib/utils";
import { Logo } from "./Logo";

/**
 * Renders the REAL Technomate logo from /public.
 *   - /logo.png       → shown on LIGHT backgrounds (dark-text version)
 *   - /logo-dark.png  → shown on DARK backgrounds (light/white-text version)
 *
 * Only /logo.png is required. If /logo-dark.png is missing, the dark-mode image
 * uses /logo.png too. If /logo.png itself isn't present yet, it falls back to
 * the built-in SVG mark + wordmark so nothing ever renders broken.
 *
 * Existence is probed with a preloaded Image() (reliable), rather than relying
 * on <img> onError timing. Size via the `className` height, e.g. "h-10".
 *
 * The files are served with a seven-day cache, so a re-export of the artwork
 * would otherwise keep showing the stale copy to anyone who had already loaded
 * the site. Bump V whenever either logo file changes to break that cache.
 */
const V = "2";
const LIGHT_SRC = `/logo.png?v=${V}`;
const DARK_SRC = `/logo-dark.png?v=${V}`;

export function BrandLogo({ className }: { className?: string }) {
  const [light, setLight] = useState<boolean | null>(null);
  const [dark, setDark] = useState<boolean | null>(null);

  useEffect(() => {
    const a = new Image();
    a.onload = () => setLight(true);
    a.onerror = () => setLight(false);
    a.src = LIGHT_SRC;

    const b = new Image();
    b.onload = () => setDark(true);
    b.onerror = () => setDark(false);
    b.src = DARK_SRC;
  }, []);

  // Still probing — reserve height, render nothing visible (avoids flash).
  if (light === null) {
    return <span className={cn("inline-block", className)} aria-hidden />;
  }

  // No real logo added yet → built-in SVG placeholder.
  if (light === false) {
    return (
      <span className="flex items-center gap-2.5">
        <Logo className={cn("w-auto", className)} />
        <span className="text-[15px] font-extrabold uppercase tracking-tight">
          Technomate<span className="text-brand-500"> IT</span>
        </span>
      </span>
    );
  }

  const darkSrc = dark ? DARK_SRC : LIGHT_SRC;
  return (
    <>
      <img
        src={LIGHT_SRC}
        alt={site.company}
        className={cn("block w-auto object-contain dark:hidden", className)}
      />
      <img
        src={darkSrc}
        alt={site.company}
        className={cn("hidden w-auto object-contain dark:block", className)}
      />
    </>
  );
}
