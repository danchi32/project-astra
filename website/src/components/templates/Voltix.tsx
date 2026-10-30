"use client";

import dynamic from "next/dynamic";
import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ShoppingCart, Star, Battery, Waves, Droplets, Mic, Bluetooth, Check, Rotate3d, ArrowRight, Search, User } from "lucide-react";
import { WebGLBoundary } from "@/components/three/WebGLBoundary";
import { TplFonts, font, In, Loop, type TplProps } from "./kit";

const VoltixScene = dynamic(() => import("./VoltixScene"), { ssr: false });

const C = { bg: "#07070c", panel: "#101018", line: "#22222f", text: "#f2f2f7", muted: "#8b8ba3", lime: "#c8ff3d" };

const finishes = [
  { name: "Midnight", color: "#2b2d3a", glow: "#c8ff3d" },
  { name: "Ocean", color: "#1e4fd8", glow: "#5ee7ff" },
  { name: "Coral", color: "#f25f4c", glow: "#ffd166" },
  { name: "Sage", color: "#7fa58d", glow: "#e9ffd1" },
];

const specs = [
  { icon: Battery, v: "24h", l: "Battery life" },
  { icon: Waves, v: "360°", l: "Room-filling sound" },
  { icon: Droplets, v: "IP67", l: "Dust & waterproof" },
  { icon: Mic, v: "4 mics", l: "Far-field voice" },
];

const models = [
  { n: "Volt Mini", p: "₹3,499", b: "12h", w: "10W" },
  { n: "Volt One", p: "₹7,999", b: "24h", w: "30W" },
  { n: "Volt Max", p: "₹14,999", b: "30h", w: "60W" },
];

/** CSS stand-in for the 3D speaker, used in gallery thumbnails and without WebGL. */
function FlatSpeaker({ color, glow }: { color: string; glow: string }) {
  return (
    <div className="relative mx-auto h-[300px] w-[180px]">
      <div className="absolute inset-x-0 top-0 h-6 rounded-[50%]" style={{ background: "#111", boxShadow: `0 0 0 3px ${glow} inset, 0 0 30px ${glow}` }} />
      <div
        className="absolute inset-x-0 top-3 bottom-4 rounded-b-[40px]"
        style={{ background: `linear-gradient(90deg, ${color}aa, ${color}, ${color}88)`, backgroundImage: `repeating-linear-gradient(0deg, transparent 0 6px, rgba(0,0,0,.18) 6px 7px), linear-gradient(90deg, ${color}99, ${color}, ${color}77)` }}
      />
      <div className="absolute inset-x-1 bottom-0 h-6 rounded-[50%] bg-gradient-to-r from-slate-400 to-slate-200" />
    </div>
  );
}

export default function Voltix({ compact, thumb }: TplProps) {
  const [fin, setFin] = useState(0);
  const [added, setAdded] = useState(false);
  const f = finishes[fin];
  const pad = compact ? "px-5" : "px-12";

  return (
    <div style={{ background: C.bg, color: C.text, fontFamily: font.grotesk }} className="relative overflow-hidden">
      <TplFonts />
      {/* Nav */}
      <header className={`flex items-center justify-between ${pad} py-5`}>
        <div className="flex items-center gap-2 text-xl font-bold tracking-tight">
          <span className="h-3 w-3 rounded-sm" style={{ background: C.lime }} /> VOLTIX
        </div>
        {!compact && (
          <nav className="flex gap-8 text-sm" style={{ color: C.muted }}>
            {["Speakers", "Headphones", "Wearables", "Support"].map((n) => (
              <span key={n}>{n}</span>
            ))}
          </nav>
        )}
        <div className="flex items-center gap-4">
          {!compact && <Search className="h-5 w-5" />}
          {!compact && <User className="h-5 w-5" />}
          <span className="relative">
            <ShoppingCart className="h-5 w-5" />
            <motion.span key={String(added)} initial={{ scale: 0 }} animate={{ scale: 1 }} className="absolute -right-2 -top-2 grid h-4 w-4 place-items-center rounded-full text-[9px] font-bold text-black" style={{ background: C.lime }}>
              {added ? 1 : 0}
            </motion.span>
          </span>
        </div>
      </header>

      {/* Hero: 3D product configurator */}
      <section className={`relative ${pad} ${compact ? "pb-10" : "grid grid-cols-[1.1fr_1fr] items-center gap-8 pb-16"}`}>
        <div className="pointer-events-none absolute left-1/2 top-10 h-[420px] w-[420px] -translate-x-1/2 rounded-full opacity-30 blur-[100px] transition-colors duration-700" style={{ background: f.glow }} />
        <div className={`relative ${compact ? "h-[340px]" : "h-[540px]"}`}>
          {thumb ? (
            <div className="grid h-full place-items-center">
              <FlatSpeaker color={f.color} glow={f.glow} />
            </div>
          ) : (
            <WebGLBoundary fallback={<div className="grid h-full place-items-center"><FlatSpeaker color={f.color} glow={f.glow} /></div>}>
              <VoltixScene color={f.color} glow={f.glow} />
            </WebGLBoundary>
          )}
          <div className="absolute bottom-3 left-1/2 flex -translate-x-1/2 items-center gap-2 rounded-full px-4 py-2 text-xs" style={{ background: C.panel, border: `1px solid ${C.line}`, color: C.muted }}>
            <Rotate3d className="h-3.5 w-3.5" /> Drag to rotate in 3D
          </div>
        </div>

        <div className="relative">
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7 }}>
            <span className="rounded-full px-3 py-1 text-xs font-bold text-black" style={{ background: C.lime }}>
              NEW · 2026
            </span>
            <h1 className={`mt-5 font-bold leading-[0.95] tracking-tight ${compact ? "text-5xl" : "text-7xl"}`}>Volt One</h1>
            <p className="mt-2 text-lg" style={{ color: C.muted }}>
              Smart speaker with 360° sound
            </p>
            <div className="mt-4 flex items-center gap-2 text-sm">
              {Array.from({ length: 5 }, (_, i) => (
                <Star key={i} className="h-4 w-4" fill={C.lime} stroke={C.lime} />
              ))}
              <span style={{ color: C.muted }}>4.8 · 2,140 reviews</span>
            </div>
            <div className="mt-6 flex items-baseline gap-3">
              <span className="text-4xl font-bold">₹7,999</span>
              <span className="line-through" style={{ color: C.muted }}>
                ₹9,999
              </span>
              <span className="text-sm font-bold" style={{ color: C.lime }}>
                20% off
              </span>
            </div>

            <div className="mt-7 text-xs font-semibold uppercase tracking-widest" style={{ color: C.muted }}>
              Finish — <span style={{ color: C.text }}>{f.name}</span>
            </div>
            <div className="mt-3 flex gap-3">
              {finishes.map((x, i) => (
                <button
                  key={x.name}
                  type="button"
                  onClick={() => setFin(i)}
                  aria-label={x.name}
                  className="h-10 w-10 rounded-full transition-transform hover:scale-110"
                  style={{ background: x.color, boxShadow: i === fin ? `0 0 0 3px ${C.bg}, 0 0 0 5px ${x.glow}` : undefined }}
                />
              ))}
            </div>

            <div className="mt-8 flex gap-3">
              <button
                type="button"
                onClick={() => setAdded(true)}
                className="flex flex-1 items-center justify-center gap-2 rounded-xl py-4 text-sm font-bold text-black transition-transform hover:-translate-y-0.5"
                style={{ background: C.lime }}
              >
                <AnimatePresence mode="wait" initial={false}>
                  <motion.span key={String(added)} initial={{ y: 10, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: -10, opacity: 0 }} className="flex items-center gap-2">
                    {added ? <Check className="h-4 w-4" /> : <ShoppingCart className="h-4 w-4" />}
                    {added ? "Added to cart" : "Add to cart"}
                  </motion.span>
                </AnimatePresence>
              </button>
              <span className="grid place-items-center rounded-xl px-6 text-sm font-bold" style={{ border: `1px solid ${C.line}` }}>
                Buy now
              </span>
            </div>
            <div className="mt-5 flex flex-wrap gap-4 text-xs" style={{ color: C.muted }}>
              <span className="flex items-center gap-1.5"><Bluetooth className="h-3.5 w-3.5" /> Bluetooth 5.3</span>
              <span>Free delivery tomorrow</span>
              <span>2-year warranty</span>
            </div>
          </motion.div>
        </div>
      </section>

      {/* Kinetic strip */}
      <div className="border-y py-5 text-3xl font-bold" style={{ borderColor: C.line }}>
        <Loop duration={18}>
          {["360° SOUND", "24H BATTERY", "IP67", "VOICE READY", "MULTI-ROOM"].map((t) => (
            <span key={t} className="mx-6 flex items-center gap-6 whitespace-nowrap">
              {t} <span style={{ color: C.lime }}>✦</span>
            </span>
          ))}
        </Loop>
      </div>

      {/* Specs */}
      <section className={`${pad} py-20`}>
        <In>
          <h2 className={`font-bold tracking-tight ${compact ? "text-3xl" : "text-5xl"}`}>
            Small speaker.
            <br />
            <span style={{ color: C.lime }}>Enormous sound.</span>
          </h2>
        </In>
        <div className={`mt-12 grid gap-4 ${compact ? "grid-cols-2" : "grid-cols-4"}`}>
          {specs.map((s, i) => (
            <In key={s.l} delay={i * 0.08}>
              <motion.div whileHover={{ y: -6 }} className="rounded-3xl p-6" style={{ background: C.panel, border: `1px solid ${C.line}` }}>
                <s.icon className="h-7 w-7" style={{ color: C.lime }} />
                <div className="mt-8 text-4xl font-bold">{s.v}</div>
                <div className="mt-1 text-sm" style={{ color: C.muted }}>
                  {s.l}
                </div>
              </motion.div>
            </In>
          ))}
        </div>
      </section>

      {/* Compare */}
      <section className={`${pad} pb-20`}>
        <In>
          <h2 className="text-3xl font-bold">Compare the range</h2>
        </In>
        <div className={`mt-8 grid gap-4 ${compact ? "grid-cols-1" : "grid-cols-3"}`}>
          {models.map((m, i) => (
            <In key={m.n} delay={i * 0.1}>
              <div className="rounded-3xl p-7" style={{ background: i === 1 ? C.lime : C.panel, color: i === 1 ? "#000" : C.text, border: `1px solid ${C.line}` }}>
                <div className="text-sm font-semibold opacity-70">{i === 1 ? "Most popular" : " "}</div>
                <div className="mt-2 text-2xl font-bold">{m.n}</div>
                <div className="mt-1 text-3xl font-bold">{m.p}</div>
                <div className="mt-6 space-y-2 text-sm">
                  <div className="flex justify-between"><span className="opacity-70">Battery</span><span>{m.b}</span></div>
                  <div className="flex justify-between"><span className="opacity-70">Output</span><span>{m.w}</span></div>
                </div>
                <div className="mt-6 flex items-center gap-1 text-sm font-bold">
                  Shop {m.n} <ArrowRight className="h-4 w-4" />
                </div>
              </div>
            </In>
          ))}
        </div>
      </section>

      <footer className={`${pad} flex justify-between border-t py-8 text-xs`} style={{ borderColor: C.line, color: C.muted }}>
        <span>© 2026 VOLTIX — sample store</span>
        <span>Shipping · Returns · Warranty</span>
      </footer>
    </div>
  );
}
