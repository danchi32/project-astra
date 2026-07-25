"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";
import { WebGLBoundary } from "./WebGLBoundary";

const AstraCoreScene = dynamic(() => import("./AstraCoreScene"), {
  ssr: false,
  loading: () => <SceneFallback pulsing />,
});

function hasWebGL(): boolean {
  try {
    const canvas = document.createElement("canvas");
    return !!(
      window.WebGLRenderingContext &&
      (canvas.getContext("webgl") || canvas.getContext("experimental-webgl"))
    );
  } catch {
    return false;
  }
}

/** Soft glowing orb shown while the scene loads or if WebGL is unavailable. */
function SceneFallback({ pulsing }: { pulsing?: boolean }) {
  return (
    <div className="absolute inset-0 grid place-items-center">
      <div
        className={cn(
          "h-40 w-40 rounded-full bg-gradient-to-br from-brand-500 to-violet-500 blur-2xl",
          pulsing && "animate-pulse",
        )}
      />
    </div>
  );
}

export function Hero3D({ className }: { className?: string }) {
  const [webgl, setWebgl] = useState<boolean | null>(null);

  useEffect(() => {
    setWebgl(hasWebGL());
  }, []);

  // R3F occasionally measures its container before layout settles (common in
  // flex/grid children), leaving the canvas at its default 300×150. A window
  // resize forces a correct re-measure — poll until the async-loaded canvas
  // exists and is properly sized, then stop.
  useEffect(() => {
    if (!webgl) return;
    let ticks = 0;
    const id = window.setInterval(() => {
      ticks += 1;
      const c = document.querySelector("canvas");
      if (c && c.clientWidth > 300) {
        window.clearInterval(id);
        return;
      }
      window.dispatchEvent(new Event("resize"));
      if (ticks > 25) window.clearInterval(id);
    }, 200);
    return () => window.clearInterval(id);
  }, [webgl]);

  return (
    <div
      className={cn(
        "relative aspect-square w-full max-w-[520px]",
        className,
      )}
    >
      {/* Ambient glow behind the canvas */}
      <div className="pointer-events-none absolute inset-8 rounded-full bg-brand-500/20 blur-3xl" />
      {webgl === false ? (
        <SceneFallback />
      ) : webgl ? (
        <WebGLBoundary fallback={<SceneFallback />}>
          <AstraCoreScene />
        </WebGLBoundary>
      ) : (
        <SceneFallback pulsing />
      )}
    </div>
  );
}
