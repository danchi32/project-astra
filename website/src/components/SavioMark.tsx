"use client";

import { useId } from "react";

/**
 * The SAVIO mark, inline so it needs no asset path and inherits nothing from the theme —
 * a logo is the one thing that should look the same in light and dark mode.
 * Source of truth: docs/brand/savio-icon.svg; the portal carries the same component. Keep them in step.
 */
export function SavioMark({ size = 32 }: { size?: number }) {
  // useId so two marks on one page (sidebar + auth panel) don't share gradient ids.
  const id = useId().replace(/:/g, "");
  return (
    <svg width={size} height={size} viewBox="0 0 128 128" role="img" aria-label="SAVIO">
      <defs>
        <linearGradient id={`${id}bg`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#3b82f6" />
          <stop offset="0.55" stopColor="#1d4ed8" />
          <stop offset="1" stopColor="#172554" />
        </linearGradient>
        <filter id={`${id}glow`} x="-1" y="-1" width="3" height="3">
          <feGaussianBlur stdDeviation="2.2" result="b" />
          <feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>
      </defs>
      <rect width="128" height="128" rx="28" fill={`url(#${id}bg)`} />
      <path d="M50 10.5 A17 17 0 0 0 50 29.5 M78 10.5 A17 17 0 0 1 78 29.5" stroke="#67e8f9" strokeWidth="3.5" strokeLinecap="round" fill="none" />
      <path d="M43 5 A25 25 0 0 0 43 35 M85 5 A25 25 0 0 1 85 35" stroke="#67e8f9" strokeWidth="3.5" strokeLinecap="round" fill="none" opacity="0.45" />
      <path d="M64 38 V30" stroke="#fff" strokeWidth="5" strokeLinecap="round" />
      <path d="M64 9 Q65.8 18.2 75 20 Q65.8 21.8 64 31 Q62.2 21.8 53 20 Q62.2 18.2 64 9 Z" fill="#fff" />
      <path d="M90 56 Q89 44 64 44 Q38 44 38 60 Q38 68 46 71 M82 87 Q90 91 90 100 Q90 112 64 112 Q39 112 38 102" stroke="#fff" strokeWidth="12" strokeLinecap="round" fill="none" />
      <rect x="33" y="66" width="62" height="24" rx="12" fill="#0b1220" stroke="#fff" strokeWidth="3" />
      <g fill="#67e8f9" filter={`url(#${id}glow)`}>
        <rect x="47" y="73" width="11" height="10" rx="5" />
        <rect x="70" y="73" width="11" height="10" rx="5" />
      </g>
      <path d="M48 58 H56 L60 52 L65 63 L69 55 L72 58 H82" stroke="#67e8f9" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" fill="none" />
      <g fill="#67e8f9">
        <rect x="52" y="99" width="4" height="6" rx="1.5" />
        <rect x="59" y="96" width="4" height="9" rx="1.5" />
        <rect x="66" y="98" width="4" height="7" rx="1.5" />
        <rect x="73" y="94" width="4" height="11" rx="1.5" />
      </g>
    </svg>
  );
}

/** Mark + wordmark, the way the logo is laid out in docs/brand/savio-logo.svg. */
export function SavioLogo({ size = 32, tagline }: { size?: number; tagline?: string }) {
  return (
    <span className="inline-flex items-center gap-2.5">
      <SavioMark size={size} />
      <span className="flex flex-col leading-none">
        <span className="font-extrabold tracking-wider" style={{ fontSize: size * 0.62, color: "var(--text-primary)" }}>
          SAV<span style={{ color: "var(--accent)" }}>IO</span>
        </span>
        {tagline && (
          <span className="mt-1 text-[10px] font-semibold uppercase tracking-[0.14em]" style={{ color: "var(--text-secondary)" }}>
            {tagline}
          </span>
        )}
      </span>
    </span>
  );
}
