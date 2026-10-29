"use client";

import { motion } from "framer-motion";
import { ArrowUpRight, ArrowDown } from "lucide-react";
import { TplFonts, font, In, Loop, type TplProps } from "./kit";

const C = { bg: "#0a0a0a", text: "#f3efe6", muted: "#8a8578", pink: "#ff2e88", violet: "#7b61ff", line: "#262626" };

const work = [
  { n: "Aurora Coffee", t: "Brand identity", bg: `linear-gradient(135deg, #ff9a3c, #ff2e88)` },
  { n: "Volt EV", t: "Website & motion", bg: `linear-gradient(135deg, #7b61ff, #00d4ff)` },
  { n: "Northwind", t: "Campaign", bg: `linear-gradient(135deg, #00c896, #c8ff3d)` },
  { n: "Mira Skin", t: "Packaging", bg: `linear-gradient(135deg, #ffd1dc, #ff6fa5)` },
];

/** The circular "available for projects" badge with rotating text. */
function SpinBadge() {
  return (
    <motion.svg viewBox="0 0 120 120" className="h-28 w-28" animate={{ rotate: 360 }} transition={{ duration: 14, repeat: Infinity, ease: "linear" }}>
      <defs>
        <path id="circ" d="M60,60 m-46,0 a46,46 0 1,1 92,0 a46,46 0 1,1 -92,0" />
      </defs>
      <text fill={C.text} fontSize="11" fontWeight="700" letterSpacing="3.2">
        <textPath href="#circ">AVAILABLE FOR PROJECTS • 2026 • </textPath>
      </text>
      <circle cx="60" cy="60" r="16" fill={C.pink} />
    </motion.svg>
  );
}

export default function Studio({ compact }: TplProps) {
  const pad = compact ? "px-5" : "px-12";
  const big = compact ? "text-4xl" : "text-[124px]";
  const lines = ["We make", "brands", "impossible", "to ignore."];

  return (
    <div style={{ background: C.bg, color: C.text, fontFamily: font.syne }} className="relative overflow-hidden">
      <TplFonts />
      <header className={`relative z-10 flex items-center justify-between ${pad} py-6 text-sm font-bold`}>
        <span className="text-lg">STUDIO/9</span>
        {!compact && (
          <span className="flex gap-8" style={{ color: C.muted }}>
            {["Work", "Services", "Studio", "Journal"].map((n) => (
              <span key={n}>{n}</span>
            ))}
          </span>
        )}
        <span className="flex items-center gap-2">
          Menu <span className="h-2.5 w-2.5 rounded-full" style={{ background: C.pink }} />
        </span>
      </header>

      {/* Hero */}
      <section className={`relative ${pad} pb-16 pt-10`}>
        <motion.div
          className="pointer-events-none absolute right-[8%] top-10 h-[420px] w-[420px] opacity-80 blur-2xl"
          style={{ background: `conic-gradient(from 0deg, ${C.pink}, ${C.violet}, #00d4ff, ${C.pink})` }}
          animate={{
            borderRadius: ["42% 58% 70% 30% / 45% 45% 55% 55%", "70% 30% 46% 54% / 30% 39% 61% 70%", "42% 58% 70% 30% / 45% 45% 55% 55%"],
            rotate: [0, 120, 360],
          }}
          transition={{ duration: 14, repeat: Infinity, ease: "linear" }}
        />
        <h1 className={`relative font-extrabold uppercase leading-[0.86] tracking-[-0.04em] ${big}`}>
          {lines.map((l, i) => (
            <span key={l} className="block overflow-hidden">
              <motion.span
                className="block"
                initial={{ y: "105%" }}
                animate={{ y: 0 }}
                transition={{ duration: 0.9, delay: 0.1 + i * 0.12, ease: [0.76, 0, 0.24, 1] }}
                style={i === 2 ? { WebkitTextStroke: `2px ${C.text}`, color: "transparent" } : undefined}
              >
                {l}
              </motion.span>
            </span>
          ))}
        </h1>
        <div className={`relative mt-10 flex ${compact ? "flex-col gap-6" : "items-end justify-between"}`}>
          <p className="max-w-md text-base" style={{ color: C.muted }}>
            An independent studio crafting identities, websites and campaigns for ambitious companies.
          </p>
          <div className="flex items-center gap-6">
            <ArrowDown className="h-6 w-6 animate-bounce" />
            <SpinBadge />
          </div>
        </div>
      </section>

      {/* Kinetic marquee, two rows in opposite directions */}
      <div className="border-y py-6" style={{ borderColor: C.line }}>
        <Loop duration={24}>
          {["Branding", "Web design", "Motion", "Strategy", "3D"].map((t) => (
            <span key={t} className="mx-6 flex items-center gap-12 whitespace-nowrap text-6xl font-extrabold uppercase">
              {t} <span style={{ color: C.pink }}>✦</span>
            </span>
          ))}
        </Loop>
        <Loop duration={30} reverse className="mt-3">
          {["Packaging", "Campaigns", "Identity", "Product", "Content"].map((t) => (
            <span key={t} className="mx-6 flex items-center gap-12 whitespace-nowrap text-6xl font-extrabold uppercase" style={{ WebkitTextStroke: `1.5px ${C.muted}`, color: "transparent" }}>
              {t} <span style={{ WebkitTextStroke: "0", color: C.violet }}>●</span>
            </span>
          ))}
        </Loop>
      </div>

      {/* Work grid */}
      <section className={`${pad} py-20`}>
        <div className="flex items-end justify-between">
          <h2 className={`font-extrabold uppercase ${compact ? "text-4xl" : "text-6xl"}`}>Selected work</h2>
          <span className="text-sm" style={{ color: C.muted }}>(04)</span>
        </div>
        <div className={`mt-10 grid gap-6 ${compact ? "grid-cols-1" : "grid-cols-2"}`}>
          {work.map((w, i) => (
            <In key={w.n} delay={(i % 2) * 0.12} y={60} className={!compact && i % 2 ? "mt-24" : ""}>
              <div className="group cursor-pointer">
                <div className="relative overflow-hidden rounded-xl" style={{ aspectRatio: "4/3" }}>
                  <div className="absolute inset-0 transition-transform duration-700 group-hover:scale-110" style={{ background: w.bg }} />
                  <motion.div className="absolute left-1/2 top-1/2 h-40 w-40 -translate-x-1/2 -translate-y-1/2 rounded-full bg-white/25 backdrop-blur" animate={{ scale: [1, 1.15, 1] }} transition={{ duration: 4 + i, repeat: Infinity }} />
                  <div className="absolute left-[18%] top-[22%] h-16 w-16 rotate-12 rounded-2xl bg-black/20 transition-transform duration-700 group-hover:rotate-45" />
                  <div className="absolute inset-0 flex items-end justify-between p-6 opacity-0 transition-opacity duration-300 group-hover:opacity-100">
                    <span className="rounded-full bg-black px-4 py-2 text-xs font-bold">View case</span>
                    <span className="grid h-12 w-12 place-items-center rounded-full bg-white text-black">
                      <ArrowUpRight className="h-5 w-5" />
                    </span>
                  </div>
                </div>
                <div className="mt-4 flex justify-between text-sm font-bold">
                  <span>{w.n}</span>
                  <span style={{ color: C.muted }}>{w.t}</span>
                </div>
              </div>
            </In>
          ))}
        </div>
      </section>

      {/* Services rows */}
      <section className={`${pad} pb-20`}>
        {["Brand identity", "Websites & products", "Motion & 3D", "Campaigns"].map((s, i) => (
          <In key={s} delay={i * 0.06}>
            <div className="group flex items-center justify-between border-t py-7 transition-all hover:px-4" style={{ borderColor: C.line }}>
              <span className="flex items-baseline gap-6">
                <span className="text-sm" style={{ color: C.muted }}>0{i + 1}</span>
                <span className={`font-extrabold uppercase transition-colors group-hover:text-[#ff2e88] ${compact ? "text-2xl" : "text-5xl"}`}>{s}</span>
              </span>
              <ArrowUpRight className="h-8 w-8 transition-transform group-hover:rotate-45" />
            </div>
          </In>
        ))}
      </section>

      {/* Footer CTA */}
      <footer className={`${pad} pb-12`}>
        <div className="rounded-3xl p-10" style={{ background: C.pink, color: "#0a0a0a" }}>
          <div className="text-sm font-bold uppercase">Have a project?</div>
          <div className={`mt-2 flex items-center gap-4 font-extrabold uppercase leading-none ${compact ? "text-5xl" : "text-[110px]"}`}>
            Let&apos;s talk
            <motion.span animate={{ x: [0, 16, 0] }} transition={{ duration: 1.6, repeat: Infinity }}>
              <ArrowUpRight className={compact ? "h-10 w-10" : "h-24 w-24"} />
            </motion.span>
          </div>
        </div>
        <div className="mt-8 flex justify-between text-xs" style={{ color: C.muted }}>
          <span>© 2026 STUDIO/9 — sample portfolio</span>
          <span>Instagram · Behance · Dribbble</span>
        </div>
      </footer>
    </div>
  );
}
