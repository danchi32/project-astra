"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { SkipForward } from "lucide-react";
import { hasWebGL } from "./Hero3D";
import { WebGLBoundary } from "./WebGLBoundary";

const TechnomateIntroScene = dynamic(() => import("./TechnomateIntroScene"), { ssr: false });

// Duplicated from TechnomateIntroScene rather than imported: importing it here
// would pull three.js into this chunk and defeat the dynamic import above.
const INTRO_SECONDS = 3.6;
// Where the scene frames the finished logo: 80% of the width, or 62% of the
// height if that is tighter. Must match Stage's fitW / fitH.
const FIT_W = 0.8;
const FIT_H = 0.62;
const FLY_SECONDS = 1;

// Same cache-buster as BrandLogo: the intro is cut from these very files.
const LIGHT_SRC = "/logo.png?v=4";
const DARK_SRC = "/logo-dark.png?v=4";

type Rect = { left: number; top: number; width: number };

function Finish({ onFinish }: { onFinish: () => void }) {
  useEffect(onFinish, [onFinish]);
  return null;
}

/**
 * Full-screen intro for the about page: the real logo assembles in 3D, then
 * flies up into the navbar's logo slot while the backdrop fades, and the page
 * content comes in.
 *
 * The flight is a hand-off: the 3D scene lands flat and centred at a size this
 * component can work out (FIT_W / FIT_H), so the canvas is swapped for the PNG
 * at exactly that spot and the PNG animates to the navbar logo's rect. The
 * navbar logo is hidden (html.tm-intro-active) until the PNG reaches it.
 *
 * onReveal fires as the flight starts (bring the content in), onFinish when it
 * lands (unmount this). Skipped outright without WebGL or with
 * prefers-reduced-motion, and it gives up if the scene has not started in 6s.
 */
export function TechnomateIntro({ onReveal, onFinish }: { onReveal: () => void; onFinish: () => void }) {
  const [src, setSrc] = useState<string | null>(null);
  const [ready, setReady] = useState(false);
  const [flight, setFlight] = useState<{ from: Rect; to: Rect } | null>(null);
  const imgAspect = useRef(0.385);
  const stage = useRef<"play" | "fly" | "done">("play");

  const end = useCallback(() => {
    if (stage.current === "done") return;
    stage.current = "done";
    document.documentElement.classList.remove("tm-intro-active");
    onReveal();
    onFinish();
  }, [onReveal, onFinish]);

  const fly = useCallback(() => {
    if (stage.current !== "play") return;
    const slot = [...document.querySelectorAll<HTMLImageElement>("[data-brand-logo] img")].find(
      (el) => el.getBoundingClientRect().width > 0,
    );
    if (!slot) return end();
    stage.current = "fly";
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    const width = Math.min(FIT_W * vw, (FIT_H * vh) / imgAspect.current);
    const r = slot.getBoundingClientRect();
    setFlight({
      from: { left: (vw - width) / 2, top: (vh - width * imgAspect.current) / 2, width },
      to: { left: r.left, top: r.top, width: r.width },
    });
    onReveal();
  }, [end, onReveal]);

  useEffect(() => {
    if (!hasWebGL() || window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      end();
      return;
    }
    const s = document.documentElement.classList.contains("dark") ? DARK_SRC : LIGHT_SRC;
    const probe = new Image();
    probe.onload = () => (imgAspect.current = probe.naturalHeight / probe.naturalWidth);
    probe.src = s;
    setSrc(s);
    window.scrollTo({ top: 0, behavior: "instant" });
    const html = document.documentElement;
    const prev = html.style.overflow;
    html.style.overflow = "hidden";
    html.classList.add("tm-intro-active");
    return () => {
      html.style.overflow = prev;
      html.classList.remove("tm-intro-active");
    };
  }, [end]);

  useEffect(() => {
    if (ready) return;
    const id = window.setTimeout(end, 6000);
    return () => window.clearTimeout(id);
  }, [ready, end]);

  return (
    <div id="tm-intro" className="fixed inset-0 z-[100]">
      <motion.div
        className="absolute inset-0 overflow-hidden bg-app"
        animate={{ opacity: flight ? 0 : 1 }}
        transition={{ duration: FLY_SECONDS * 0.8, ease: "easeOut" }}
      >
        <div className="aurora pointer-events-none absolute inset-0" />
        <div className="grid-bg pointer-events-none absolute inset-0 opacity-60 [mask-image:radial-gradient(ellipse_at_center,black,transparent_70%)]" />
        <div className="pointer-events-none absolute left-1/2 top-1/2 h-[28rem] w-[28rem] -translate-x-1/2 -translate-y-1/2 rounded-full bg-blue-500/20 blur-3xl" />

        {src && !flight && (
          <div className="absolute inset-0">
            <WebGLBoundary fallback={<Finish onFinish={end} />}>
              <TechnomateIntroScene src={src} onReady={() => setReady(true)} onDone={fly} />
            </WebGLBoundary>
          </div>
        )}

        {!flight && (
          <>
            <button
              type="button"
              onClick={ready ? fly : end}
              className="absolute right-5 top-5 flex items-center gap-1.5 rounded-full border border-token bg-surface/80 px-4 py-2 text-xs font-semibold text-secondary-token backdrop-blur transition hover:text-primary-token"
            >
              Skip <SkipForward className="h-3.5 w-3.5" />
            </button>
            <div className="absolute bottom-8 left-1/2 h-1 w-40 -translate-x-1/2 overflow-hidden rounded-full bg-brand-500/15">
              {ready && (
                <div
                  className="tm-progress h-full rounded-full bg-gradient-to-r from-brand-600 to-cyan-400"
                  style={{ animationDuration: `${INTRO_SECONDS}s` }}
                />
              )}
            </div>
          </>
        )}
      </motion.div>

      {flight && src && (
        <motion.img
          src={src}
          alt=""
          className="absolute left-0 top-0 max-w-none"
          initial={flight.from}
          animate={flight.to}
          transition={{ duration: FLY_SECONDS, ease: [0.65, 0, 0.35, 1] }}
          onAnimationComplete={end}
        />
      )}
    </div>
  );
}
