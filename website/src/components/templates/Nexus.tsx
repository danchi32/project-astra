"use client";

import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowUpRight, Cloud, ShieldCheck, Database, Cpu, Globe2, Activity, Check } from "lucide-react";
import { TplFonts, font, In, Loop, type TplProps } from "./kit";

const C = { bg: "#f6f8fc", ink: "#0a1633", muted: "#5a6785", blue: "#2457ff", line: "#e2e8f4", card: "#ffffff" };
const words = ["cloud", "security", "data", "AI"];

/** Three floating slabs in isometric projection — pure CSS 3D. */
function IsoStack() {
  const layers = [
    { label: "Data & AI", icon: Database, from: "#7aa2ff", to: "#2457ff" },
    { label: "Security", icon: ShieldCheck, from: "#5ee7ff", to: "#0ea5e9" },
    { label: "Cloud", icon: Cloud, from: "#c4d4ff", to: "#7aa2ff" },
  ];
  return (
    <div className="relative grid h-[420px] place-items-center" style={{ perspective: 1400 }}>
      <div style={{ transform: "rotateX(58deg) rotateZ(-42deg)", transformStyle: "preserve-3d" }} className="relative h-56 w-56">
        {layers.map((l, i) => (
          <motion.div
            key={l.label}
            className="absolute inset-0 rounded-3xl"
            style={{
              background: `linear-gradient(135deg, ${l.from}, ${l.to})`,
              boxShadow: "0 30px 60px -10px rgba(36,87,255,.45), inset 0 0 0 1px rgba(255,255,255,.4)",
              transformStyle: "preserve-3d",
            }}
            initial={{ z: 0, opacity: 0 }}
            animate={{ z: [i * 70, i * 70 + 18, i * 70], opacity: 1 }}
            transition={{ z: { duration: 4, repeat: Infinity, ease: "easeInOut", delay: i * 0.4 }, opacity: { duration: 0.6, delay: i * 0.2 } }}
          >
            <div className="absolute inset-0 grid place-items-center">
              <l.icon className="h-16 w-16 text-white/90" strokeWidth={1.4} />
            </div>
            <div className="absolute inset-3 rounded-2xl border border-white/30" />
          </motion.div>
        ))}
      </div>
      {/* Floating labels */}
      {[
        { t: "99.98% uptime", c: "top-10 right-6" },
        { t: "SOC-ready security", c: "bottom-16 left-0" },
        { t: "40% lower cloud cost", c: "bottom-4 right-10" },
      ].map((b, i) => (
        <motion.div
          key={b.t}
          className={`absolute ${b.c} flex items-center gap-2 rounded-full bg-white px-4 py-2 text-xs font-semibold shadow-xl`}
          animate={{ y: [0, -8, 0] }}
          transition={{ duration: 3 + i, repeat: Infinity, ease: "easeInOut" }}
        >
          <span className="h-2 w-2 rounded-full" style={{ background: C.blue }} /> {b.t}
        </motion.div>
      ))}
    </div>
  );
}

export default function Nexus({ compact }: TplProps) {
  const [w, setW] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setW((x) => (x + 1) % words.length), 2200);
    return () => clearInterval(id);
  }, []);
  const pad = compact ? "px-5" : "px-14";

  return (
    <div style={{ background: C.bg, color: C.ink, fontFamily: font.manrope }} className="overflow-hidden">
      <TplFonts />
      <header className={`flex items-center justify-between ${pad} py-6`}>
        <div className="flex items-center gap-2.5 text-lg font-extrabold">
          <span className="grid h-9 w-9 place-items-center rounded-xl text-white" style={{ background: C.ink }}>
            N
          </span>
          Nexus
        </div>
        {!compact && (
          <nav className="flex items-center gap-1 rounded-full bg-white p-1 text-sm font-medium shadow-sm" style={{ color: C.muted }}>
            {["Services", "Industries", "Case studies", "Company"].map((n, i) => (
              <span key={n} className="rounded-full px-4 py-2" style={i === 0 ? { background: C.bg, color: C.ink } : undefined}>
                {n}
              </span>
            ))}
          </nav>
        )}
        <span className="rounded-full px-5 py-2.5 text-sm font-bold text-white" style={{ background: C.blue }}>
          Talk to us
        </span>
      </header>

      {/* Hero */}
      <section className={`${pad} ${compact ? "pt-8" : "grid grid-cols-2 items-center gap-10 pt-10"}`}>
        <div>
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="inline-flex items-center gap-2 rounded-full bg-white px-3 py-1.5 text-xs font-semibold shadow-sm">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full opacity-75" style={{ background: C.blue }} />
              <span className="relative inline-flex h-2 w-2 rounded-full" style={{ background: C.blue }} />
            </span>
            Trusted by 200+ growing companies
          </motion.div>
          <h1 className={`mt-6 font-extrabold leading-[1.02] tracking-tight ${compact ? "text-4xl" : "text-6xl"}`}>
            IT that scales
            <br />
            your{" "}
            <span className="relative inline-block" style={{ color: C.blue }}>
              <AnimatePresence mode="wait">
                <motion.span key={w} initial={{ y: "100%", opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: "-100%", opacity: 0 }} transition={{ duration: 0.4 }} className="inline-block">
                  {words[w]}.
                </motion.span>
              </AnimatePresence>
            </span>
          </h1>
          <p className="mt-6 max-w-lg text-lg" style={{ color: C.muted }}>
            Consulting, cloud and managed services for companies that want enterprise-grade IT without enterprise headaches.
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-4">
            <span className="inline-flex items-center gap-2 rounded-full px-6 py-3.5 text-sm font-bold text-white" style={{ background: C.ink }}>
              Book a free audit <ArrowUpRight className="h-4 w-4" />
            </span>
            <div className="flex items-center gap-3">
              <div className="flex -space-x-2">
                {["#2457ff", "#0ea5e9", "#7c3aed", "#f59e0b"].map((c) => (
                  <span key={c} className="h-9 w-9 rounded-full border-2 border-white" style={{ background: c }} />
                ))}
              </div>
              <span className="text-xs font-semibold" style={{ color: C.muted }}>
                4.9/5 from 300+ reviews
              </span>
            </div>
          </div>
        </div>
        <IsoStack />
      </section>

      {/* Logos */}
      <div className={`${pad} py-10`}>
        <div className="mb-5 text-center text-xs font-semibold uppercase tracking-widest" style={{ color: C.muted }}>
          Powering teams at
        </div>
        <Loop duration={26}>
          {["Acme Corp", "Globex", "Initech", "Umbrella", "Hooli", "Stark Ind.", "Wayne Ent.", "Soylent"].map((l) => (
            <span key={l} className="mx-10 whitespace-nowrap text-2xl font-extrabold opacity-30">
              {l}
            </span>
          ))}
        </Loop>
      </div>

      {/* Bento */}
      <section className={`${pad} py-14`}>
        <In>
          <h2 className={`max-w-2xl font-extrabold tracking-tight ${compact ? "text-3xl" : "text-5xl"}`}>Everything your IT needs, in one partner.</h2>
        </In>
        <div className={`mt-10 grid gap-4 ${compact ? "grid-cols-1" : "grid-cols-3 grid-rows-2"}`}>
          <In className={compact ? "" : "col-span-2"}>
            <div className="h-full rounded-3xl p-8 text-white" style={{ background: C.ink }}>
              <Activity className="h-6 w-6" />
              <div className="mt-3 text-2xl font-extrabold">Live infrastructure monitoring</div>
              <div className="mt-1 text-sm opacity-70">Every server, every app, every minute.</div>
              <div className="mt-8 flex h-32 items-end gap-2">
                {[40, 65, 50, 80, 60, 90, 70, 85, 55, 95, 75, 88].map((h, i) => (
                  <motion.div
                    key={i}
                    className="flex-1 rounded-t-md"
                    style={{ background: i === 9 ? "#5ee7ff" : "rgba(255,255,255,.18)" }}
                    initial={{ height: 0 }}
                    whileInView={{ height: `${h}%` }}
                    viewport={{ once: true }}
                    transition={{ delay: i * 0.05, duration: 0.6 }}
                  />
                ))}
              </div>
            </div>
          </In>
          <In delay={0.1}>
            <div className="relative h-full overflow-hidden rounded-3xl p-8" style={{ background: C.card, border: `1px solid ${C.line}` }}>
              <ShieldCheck className="h-6 w-6" style={{ color: C.blue }} />
              <div className="mt-3 text-xl font-extrabold">Zero-trust security</div>
              <div className="mt-1 text-sm" style={{ color: C.muted }}>Threats blocked before they land.</div>
              <motion.div className="absolute -bottom-10 -right-10 h-40 w-40 rounded-full" style={{ border: `2px solid ${C.blue}` }} animate={{ scale: [1, 1.4], opacity: [0.6, 0] }} transition={{ duration: 2, repeat: Infinity }} />
              <motion.div className="absolute -bottom-10 -right-10 h-40 w-40 rounded-full" style={{ border: `2px solid ${C.blue}` }} animate={{ scale: [1, 1.4], opacity: [0.6, 0] }} transition={{ duration: 2, repeat: Infinity, delay: 1 }} />
            </div>
          </In>
          <In delay={0.15}>
            <div className="h-full rounded-3xl p-8" style={{ background: C.blue, color: "#fff" }}>
              <div className="text-6xl font-extrabold">99.98%</div>
              <div className="mt-2 text-sm opacity-80">Average uptime across client systems</div>
            </div>
          </In>
          <In delay={0.2}>
            <div className="h-full rounded-3xl p-8" style={{ background: C.card, border: `1px solid ${C.line}` }}>
              <Cpu className="h-6 w-6" style={{ color: C.blue }} />
              <div className="mt-3 text-xl font-extrabold">AI automation</div>
              <div className="mt-1 text-sm" style={{ color: C.muted }}>Routine IT tickets resolved automatically.</div>
            </div>
          </In>
          <In delay={0.25}>
            <div className="h-full rounded-3xl p-8" style={{ background: C.card, border: `1px solid ${C.line}` }}>
              <Globe2 className="h-6 w-6" style={{ color: C.blue }} />
              <div className="mt-3 text-xl font-extrabold">Multi-cloud</div>
              <div className="mt-3 flex flex-wrap gap-2">
                {["AWS", "Azure", "GCP", "On-prem"].map((x) => (
                  <span key={x} className="rounded-full px-3 py-1 text-xs font-semibold" style={{ background: C.bg }}>
                    {x}
                  </span>
                ))}
              </div>
            </div>
          </In>
        </div>
      </section>

      {/* Process */}
      <section className={`${pad} py-14`}>
        <In>
          <h2 className={`font-extrabold tracking-tight ${compact ? "text-3xl" : "text-4xl"}`}>How we work</h2>
        </In>
        <div className={`relative mt-10 grid gap-6 ${compact ? "grid-cols-1" : "grid-cols-4"}`}>
          {!compact && (
            <motion.div className="absolute left-0 right-0 top-6 h-0.5 origin-left" style={{ background: C.blue }} initial={{ scaleX: 0 }} whileInView={{ scaleX: 1 }} viewport={{ once: true }} transition={{ duration: 1.4 }} />
          )}
          {["Audit", "Roadmap", "Migrate", "Run & improve"].map((s, i) => (
            <In key={s} delay={0.2 + i * 0.15} className="relative">
              <span className="relative z-10 grid h-12 w-12 place-items-center rounded-full bg-white text-lg font-extrabold shadow-md" style={{ color: C.blue, border: `2px solid ${C.blue}` }}>
                {i + 1}
              </span>
              <div className="mt-4 text-lg font-extrabold">{s}</div>
              <div className="mt-1 text-sm" style={{ color: C.muted }}>
                {["We map every system and risk.", "A clear, costed plan.", "Moved with zero downtime.", "24/7 support and reviews."][i]}
              </div>
            </In>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className={`${pad} pb-14`}>
        <div className="relative overflow-hidden rounded-[32px] p-12 text-white" style={{ background: `linear-gradient(120deg, ${C.ink}, #1b3a8f)` }}>
          <motion.div className="absolute -right-20 -top-20 h-72 w-72 rounded-full blur-3xl" style={{ background: C.blue }} animate={{ x: [0, -40, 0], y: [0, 30, 0] }} transition={{ duration: 8, repeat: Infinity }} />
          <div className={`relative ${compact ? "text-3xl" : "text-5xl"} max-w-2xl font-extrabold tracking-tight`}>Ready to stop worrying about IT?</div>
          <div className="relative mt-6 flex flex-wrap gap-4 text-sm">
            {["Free IT audit", "No lock-in contracts", "Response in 15 minutes"].map((x) => (
              <span key={x} className="flex items-center gap-2">
                <Check className="h-4 w-4" style={{ color: "#5ee7ff" }} /> {x}
              </span>
            ))}
          </div>
          <span className="relative mt-8 inline-flex items-center gap-2 rounded-full bg-white px-6 py-3.5 text-sm font-bold" style={{ color: C.ink }}>
            Book your audit <ArrowUpRight className="h-4 w-4" />
          </span>
        </div>
      </section>
      <footer className={`${pad} flex justify-between pb-10 text-xs`} style={{ color: C.muted }}>
        <span>© 2026 Nexus Solutions — sample site</span>
        <span>LinkedIn · Careers · Privacy</span>
      </footer>
    </div>
  );
}
