"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Sparkles, Zap, BarChart3, Lock, Workflow, Users, Check, Plus, LayoutDashboard, Inbox, Settings, Rocket } from "lucide-react";
import { TplFonts, font, In, type TplProps } from "./kit";

const C = { bg: "#0b0920", panel: "#141130", line: "#2a2550", text: "#efedff", muted: "#9c97c9", violet: "#7c5cff", cyan: "#3ee6ff" };

const plans = [
  { n: "Starter", m: 0, y: 0, d: "For individuals getting started", f: ["3 projects", "Basic automations", "Community support"] },
  { n: "Team", m: 499, y: 399, d: "For growing teams", f: ["Unlimited projects", "Advanced automations", "Insights dashboard", "Priority support"], hot: true },
  { n: "Business", m: 899, y: 719, d: "For organisations at scale", f: ["Everything in Team", "SSO & audit logs", "Custom roles", "Dedicated manager"] },
];

const faqs = [
  { q: "Is there a free trial?", a: "Yes — every paid plan has a 14-day free trial, no card required." },
  { q: "Can I import from other tools?", a: "One-click import from spreadsheets, Trello, Jira and Asana." },
  { q: "Is my data secure?", a: "Encrypted in transit and at rest, with SSO, roles and audit logs." },
];

function Dashboard({ compact }: { compact?: boolean }) {
  return (
    <div className="overflow-hidden rounded-2xl" style={{ background: C.panel, border: `1px solid ${C.line}`, boxShadow: `0 40px 120px -20px ${C.violet}66` }}>
      <div className="flex items-center gap-1.5 px-4 py-3" style={{ borderBottom: `1px solid ${C.line}` }}>
        {["#ff5f57", "#febc2e", "#28c840"].map((c) => (
          <span key={c} className="h-2.5 w-2.5 rounded-full" style={{ background: c }} />
        ))}
      </div>
      <div className="flex">
        {!compact && (
          <div className="w-44 space-y-1 p-3 text-xs" style={{ borderRight: `1px solid ${C.line}`, color: C.muted }}>
            {[LayoutDashboard, Inbox, Workflow, Users, Settings].map((I, i) => (
              <div key={i} className="flex items-center gap-2 rounded-lg px-3 py-2" style={i === 0 ? { background: C.violet + "33", color: C.text } : undefined}>
                <I className="h-3.5 w-3.5" /> {["Overview", "Inbox", "Automations", "Team", "Settings"][i]}
              </div>
            ))}
          </div>
        )}
        <div className="flex-1 p-5">
          <div className={`grid gap-3 ${compact ? "grid-cols-2" : "grid-cols-3"}`}>
            {[
              { l: "Tasks done", v: "1,284", c: C.cyan },
              { l: "On-time", v: "96%", c: C.violet },
              { l: "Hours saved", v: "312", c: "#ff7ab6" },
            ]
              .slice(0, compact ? 2 : 3)
              .map((k) => (
                <div key={k.l} className="rounded-xl p-3" style={{ background: C.bg }}>
                  <div className="text-[10px]" style={{ color: C.muted }}>{k.l}</div>
                  <div className="mt-1 text-xl font-bold" style={{ color: k.c }}>{k.v}</div>
                </div>
              ))}
          </div>
          <div className="mt-3 flex h-28 items-end gap-1.5 rounded-xl p-3" style={{ background: C.bg }}>
            {[30, 45, 38, 60, 52, 75, 64, 82, 70, 92, 85, 98].map((h, i) => (
              <motion.div
                key={i}
                className="flex-1 rounded-t"
                style={{ background: `linear-gradient(to top, ${C.violet}, ${C.cyan})` }}
                initial={{ height: "10%" }}
                animate={{ height: [`${h * 0.5}%`, `${h}%`, `${h * 0.8}%`] }}
                transition={{ duration: 3, delay: i * 0.08, repeat: Infinity, repeatType: "reverse" }}
              />
            ))}
          </div>
          <div className={`mt-3 grid gap-2 ${compact ? "grid-cols-1" : "grid-cols-3"}`}>
            {["To do", "In progress", "Done"].slice(0, compact ? 1 : 3).map((col, ci) => (
              <div key={col} className="rounded-xl p-2" style={{ background: C.bg }}>
                <div className="mb-2 text-[10px] font-semibold" style={{ color: C.muted }}>{col}</div>
                {[0, 1].map((j) => (
                  <motion.div key={j} className="mb-1.5 rounded-lg p-2 text-[10px]" style={{ background: C.panel }} animate={{ y: [0, -2, 0] }} transition={{ duration: 2, repeat: Infinity, delay: ci * 0.3 + j * 0.2 }}>
                    <div className="h-1.5 w-3/4 rounded" style={{ background: C.line }} />
                    <div className="mt-1.5 h-1.5 w-1/2 rounded" style={{ background: [C.violet, C.cyan, "#ff7ab6"][ci] + "88" }} />
                  </motion.div>
                ))}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function Launchly({ compact }: TplProps) {
  const [yearly, setYearly] = useState(true);
  const [faq, setFaq] = useState(0);
  const pad = compact ? "px-5" : "px-14";

  return (
    <div style={{ background: C.bg, color: C.text, fontFamily: font.jakarta }} className="relative overflow-hidden">
      <TplFonts />
      {/* Background glow + grid */}
      <div className="pointer-events-none absolute inset-x-0 top-0 h-[900px]" style={{ backgroundImage: `linear-gradient(${C.line}55 1px, transparent 1px), linear-gradient(90deg, ${C.line}55 1px, transparent 1px)`, backgroundSize: "56px 56px", maskImage: "radial-gradient(ellipse at top, black, transparent 70%)" }} />
      <motion.div className="pointer-events-none absolute left-1/4 top-20 h-96 w-96 rounded-full blur-[120px]" style={{ background: C.violet }} animate={{ x: [0, 80, 0], opacity: [0.5, 0.8, 0.5] }} transition={{ duration: 10, repeat: Infinity }} />
      <motion.div className="pointer-events-none absolute right-1/4 top-40 h-80 w-80 rounded-full blur-[120px]" style={{ background: C.cyan }} animate={{ x: [0, -60, 0], opacity: [0.3, 0.6, 0.3] }} transition={{ duration: 9, repeat: Infinity }} />

      <header className={`relative flex items-center justify-between ${pad} py-6`}>
        <div className="flex items-center gap-2 text-lg font-extrabold">
          <Rocket className="h-5 w-5" style={{ color: C.cyan }} /> Launchly
        </div>
        {!compact && (
          <nav className="flex gap-8 text-sm" style={{ color: C.muted }}>
            {["Product", "Features", "Pricing", "Docs"].map((n) => (
              <span key={n}>{n}</span>
            ))}
          </nav>
        )}
        <span className="rounded-full px-5 py-2.5 text-sm font-bold" style={{ background: C.text, color: C.bg }}>
          Start free
        </span>
      </header>

      {/* Hero */}
      <section className={`relative ${pad} pt-14 text-center`}>
        <motion.span initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="inline-flex items-center gap-2 rounded-full px-4 py-1.5 text-xs font-semibold" style={{ background: C.violet + "22", border: `1px solid ${C.violet}66` }}>
          <Sparkles className="h-3.5 w-3.5" style={{ color: C.cyan }} /> New: AI workflows that write themselves
        </motion.span>
        <motion.h1
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.1 }}
          className={`mx-auto mt-6 max-w-4xl font-extrabold leading-[1.02] tracking-tight ${compact ? "text-4xl" : "text-7xl"}`}
        >
          Ship projects{" "}
          <span style={{ background: `linear-gradient(90deg, ${C.violet}, ${C.cyan})`, WebkitBackgroundClip: "text", backgroundClip: "text", color: "transparent" }}>twice as fast</span>
        </motion.h1>
        <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.3 }} className="mx-auto mt-6 max-w-xl text-lg" style={{ color: C.muted }}>
          Plan, track and automate your team&apos;s work in one beautifully simple workspace.
        </motion.p>
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.45 }} className="mt-8 flex justify-center gap-3">
          <span className="rounded-full px-7 py-3.5 text-sm font-bold" style={{ background: `linear-gradient(90deg, ${C.violet}, ${C.cyan})`, color: "#fff" }}>
            Start 14-day trial
          </span>
          <span className="rounded-full px-7 py-3.5 text-sm font-bold" style={{ border: `1px solid ${C.line}` }}>
            Watch demo ▶
          </span>
        </motion.div>
        <div className="mx-auto mt-16 max-w-5xl" style={{ perspective: 1600 }}>
          <motion.div style={{ transformOrigin: "center top" }} initial={{ opacity: 0, y: 80, rotateX: 38 }} animate={{ opacity: 1, y: 0, rotateX: 0 }} transition={{ duration: 1.4, delay: 0.5, ease: [0.16, 1, 0.3, 1] }}>
            <Dashboard compact={compact} />
          </motion.div>
        </div>
      </section>

      {/* Features */}
      <section className={`relative ${pad} py-24`}>
        <In className="text-center">
          <h2 className={`font-extrabold tracking-tight ${compact ? "text-3xl" : "text-5xl"}`}>Built for teams that move fast</h2>
        </In>
        <div className={`mt-12 grid gap-4 ${compact ? "grid-cols-1" : "grid-cols-3"}`}>
          {[
            { i: Zap, t: "Automations", d: "If-this-then-that rules that run your routine work." },
            { i: BarChart3, t: "Live insights", d: "Burn-down, velocity and workload — updated in real time." },
            { i: Lock, t: "Enterprise security", d: "SSO, SCIM, roles and full audit history." },
          ].map((f, i) => (
            <In key={f.t} delay={i * 0.1}>
              <motion.div whileHover={{ y: -6, borderColor: C.violet }} className="h-full rounded-3xl p-7" style={{ background: C.panel, border: `1px solid ${C.line}` }}>
                <span className="grid h-12 w-12 place-items-center rounded-2xl" style={{ background: `linear-gradient(135deg, ${C.violet}, ${C.cyan})` }}>
                  <f.i className="h-6 w-6" />
                </span>
                <div className="mt-5 text-xl font-bold">{f.t}</div>
                <div className="mt-2 text-sm" style={{ color: C.muted }}>{f.d}</div>
              </motion.div>
            </In>
          ))}
        </div>
      </section>

      {/* Pricing */}
      <section className={`relative ${pad} pb-24 text-center`}>
        <In>
          <h2 className={`font-extrabold tracking-tight ${compact ? "text-3xl" : "text-5xl"}`}>Simple, fair pricing</h2>
          <button type="button" onClick={() => setYearly((y) => !y)} className="mt-6 inline-flex items-center gap-3 rounded-full p-1 text-sm" style={{ background: C.panel, border: `1px solid ${C.line}` }}>
            {["Monthly", "Yearly −20%"].map((l, i) => (
              <span key={l} className="relative rounded-full px-4 py-2 font-semibold">
                {(i === 1) === yearly && <motion.span layoutId="bill" className="absolute inset-0 rounded-full" style={{ background: C.violet }} />}
                <span className="relative">{l}</span>
              </span>
            ))}
          </button>
        </In>
        <div className={`mt-10 grid gap-4 text-left ${compact ? "grid-cols-1" : "grid-cols-3"}`}>
          {plans.map((p, i) => (
            <In key={p.n} delay={i * 0.1}>
              <div className="relative h-full rounded-3xl p-8" style={{ background: p.hot ? `linear-gradient(160deg, ${C.violet}, #4a2fd1)` : C.panel, border: `1px solid ${p.hot ? C.violet : C.line}` }}>
                {p.hot && <span className="absolute right-6 top-6 rounded-full bg-white/20 px-3 py-1 text-[11px] font-bold">Most popular</span>}
                <div className="text-lg font-bold">{p.n}</div>
                <div className="mt-1 text-sm opacity-70">{p.d}</div>
                <div className="mt-6 flex items-baseline gap-1">
                  <AnimatePresence mode="wait">
                    <motion.span key={String(yearly)} initial={{ y: 12, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: -12, opacity: 0 }} className="text-5xl font-extrabold">
                      {p.m === 0 ? "Free" : `₹${yearly ? p.y : p.m}`}
                    </motion.span>
                  </AnimatePresence>
                  {p.m > 0 && <span className="text-sm opacity-70">/user/mo</span>}
                </div>
                <ul className="mt-6 space-y-2.5 text-sm">
                  {p.f.map((x) => (
                    <li key={x} className="flex items-center gap-2">
                      <Check className="h-4 w-4" style={{ color: p.hot ? "#fff" : C.cyan }} /> {x}
                    </li>
                  ))}
                </ul>
                <div className="mt-8 rounded-full py-3 text-center text-sm font-bold" style={{ background: p.hot ? "#fff" : C.bg, color: p.hot ? C.violet : C.text }}>
                  Get started
                </div>
              </div>
            </In>
          ))}
        </div>
      </section>

      {/* FAQ */}
      <section className={`relative ${pad} pb-24`}>
        <div className="mx-auto max-w-2xl">
          <In>
            <h2 className="text-center text-3xl font-extrabold">Questions? Answers.</h2>
          </In>
          <div className="mt-8 space-y-3">
            {faqs.map((f, i) => (
              <button key={f.q} type="button" onClick={() => setFaq(i === faq ? -1 : i)} className="block w-full rounded-2xl p-5 text-left" style={{ background: C.panel, border: `1px solid ${C.line}` }}>
                <div className="flex items-center justify-between font-semibold">
                  {f.q}
                  <motion.span animate={{ rotate: faq === i ? 45 : 0 }}>
                    <Plus className="h-4 w-4" />
                  </motion.span>
                </div>
                <AnimatePresence initial={false}>
                  {faq === i && (
                    <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
                      <div className="pt-3 text-sm" style={{ color: C.muted }}>{f.a}</div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </button>
            ))}
          </div>
        </div>
      </section>
      <footer className={`relative ${pad} flex justify-between border-t py-8 text-xs`} style={{ borderColor: C.line, color: C.muted }}>
        <span>© 2026 Launchly — sample product</span>
        <span>Status · Security · Terms</span>
      </footer>
    </div>
  );
}
