"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Heart, HeartPulse, Brain, Bone, Baby, Eye, Stethoscope, Phone, Check, Star, ShieldPlus, Clock } from "lucide-react";
import { TplFonts, font, In, type TplProps } from "./kit";

const C = { bg: "#f2fbfa", ink: "#0d2b33", muted: "#5b767c", teal: "#0e9f9a", mint: "#d5f3ee", card: "#ffffff", red: "#ef4444", line: "#d8ecea" };

const depts = [
  { n: "Cardiology", i: HeartPulse },
  { n: "Neurology", i: Brain },
  { n: "Orthopaedics", i: Bone },
  { n: "Paediatrics", i: Baby },
  { n: "Ophthalmology", i: Eye },
  { n: "General medicine", i: Stethoscope },
];

const doctors = [
  { n: "Dr. Ananya Mehta", s: "Cardiologist", y: 15, c: "#0e9f9a", on: true },
  { n: "Dr. Sameer Khan", s: "Paediatrician", y: 11, c: "#6366f1", on: true },
  { n: "Dr. Ritu Iyer", s: "Orthopaedic surgeon", y: 18, c: "#f59e0b", on: false },
  { n: "Dr. Vikram Rao", s: "Neurologist", y: 14, c: "#ec4899", on: true },
];

/** Heart-monitor trace drawing itself on a loop. */
function Ecg() {
  const d = "M0 60 L60 60 L75 60 L85 40 L95 80 L105 10 L118 100 L128 60 L170 60 L185 50 L200 60 L260 60 L275 60 L285 40 L295 80 L305 10 L318 100 L328 60 L370 60 L385 50 L400 60";
  return (
    <svg viewBox="0 0 400 110" className="w-full">
      <path d={d} fill="none" stroke={C.line} strokeWidth="3" />
      <motion.path d={d} fill="none" stroke={C.teal} strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round" initial={{ pathLength: 0 }} animate={{ pathLength: [0, 1, 1], opacity: [1, 1, 0] }} transition={{ duration: 2.6, repeat: Infinity, times: [0, 0.8, 1], ease: "linear" }} />
    </svg>
  );
}

export default function CarePlus({ compact }: TplProps) {
  const [dept, setDept] = useState(0);
  const [day, setDay] = useState(1);
  const [slot, setSlot] = useState("10:30");
  const [done, setDone] = useState(false);
  const days = ["Mon 3", "Tue 4", "Wed 5", "Thu 6", "Fri 7"];
  const pad = compact ? "px-5" : "px-14";

  return (
    <div style={{ background: C.bg, color: C.ink, fontFamily: font.nunito }} className="overflow-hidden">
      <TplFonts />
      <div className="flex items-center justify-center gap-2 py-2 text-xs font-bold text-white" style={{ background: C.red }}>
        <span className="relative flex h-2 w-2">
          <span className="absolute h-full w-full animate-ping rounded-full bg-white" />
          <span className="relative h-2 w-2 rounded-full bg-white" />
        </span>
        24×7 Emergency: 1800-000-0000
      </div>

      <header className={`flex items-center justify-between ${pad} py-5`}>
        <span className="flex items-center gap-2 text-xl font-extrabold">
          <span className="grid h-10 w-10 place-items-center rounded-2xl text-white" style={{ background: C.teal }}>
            <ShieldPlus className="h-5 w-5" />
          </span>
          CarePlus
        </span>
        {!compact && (
          <nav className="flex gap-8 text-sm font-semibold" style={{ color: C.muted }}>
            {["Departments", "Doctors", "Health packages", "Reports"].map((n) => (
              <span key={n}>{n}</span>
            ))}
          </nav>
        )}
        <span className="flex items-center gap-2 rounded-2xl px-5 py-2.5 text-sm font-bold text-white" style={{ background: C.ink }}>
          <Phone className="h-4 w-4" /> {compact ? "" : "Call now"}
        </span>
      </header>

      {/* Hero */}
      <section className={`${pad} ${compact ? "pt-6" : "grid grid-cols-2 items-center gap-12 pt-10"}`}>
        <div>
          <motion.span initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="inline-flex items-center gap-2 rounded-full px-4 py-1.5 text-sm font-bold" style={{ background: C.mint, color: C.teal }}>
            <Star className="h-4 w-4" fill={C.teal} /> Rated 4.9 by 12,000+ patients
          </motion.span>
          <motion.h1 initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.8 }} className={`mt-6 font-extrabold leading-[1.05] tracking-tight ${compact ? "text-4xl" : "text-6xl"}`}>
            Caring for your family, <span style={{ color: C.teal }}>every heartbeat</span> of the way.
          </motion.h1>
          <p className="mt-5 max-w-lg text-lg" style={{ color: C.muted }}>
            Experienced specialists, modern diagnostics and appointments in under a minute.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <span className="rounded-2xl px-7 py-4 text-sm font-bold text-white shadow-lg" style={{ background: C.teal, boxShadow: `0 20px 40px -15px ${C.teal}` }}>
              Book appointment
            </span>
            <span className="rounded-2xl px-7 py-4 text-sm font-bold" style={{ background: C.card, border: `1px solid ${C.line}` }}>
              Find a doctor
            </span>
          </div>
        </div>
        <div className={`relative ${compact ? "mt-10" : ""}`}>
          <div className="relative rounded-[32px] p-8" style={{ background: C.card, boxShadow: "0 40px 80px -30px rgba(14,159,154,.35)" }}>
            <div className="flex items-center justify-between">
              <div>
                <div className="text-sm font-bold" style={{ color: C.muted }}>Heart rate</div>
                <div className="text-4xl font-extrabold">
                  72 <span className="text-base" style={{ color: C.muted }}>bpm</span>
                </div>
              </div>
              <motion.span animate={{ scale: [1, 1.25, 1, 1.15, 1] }} transition={{ duration: 1.2, repeat: Infinity }} className="grid h-16 w-16 place-items-center rounded-full" style={{ background: "#fee2e2" }}>
                <Heart className="h-8 w-8" fill={C.red} stroke={C.red} />
              </motion.span>
            </div>
            <div className="mt-6">
              <Ecg />
            </div>
            <div className="mt-6 grid grid-cols-3 gap-3 text-center">
              {[["98%", "SpO₂"], ["120/80", "BP"], ["36.8°", "Temp"]].map(([v, l]) => (
                <div key={l} className="rounded-2xl py-3" style={{ background: C.bg }}>
                  <div className="font-extrabold">{v}</div>
                  <div className="text-xs" style={{ color: C.muted }}>{l}</div>
                </div>
              ))}
            </div>
          </div>
          <motion.div className="absolute -left-6 -top-6 flex items-center gap-2 rounded-2xl bg-white px-4 py-3 text-sm font-bold shadow-xl" animate={{ y: [0, -10, 0] }} transition={{ duration: 3.5, repeat: Infinity }}>
            <span className="h-2.5 w-2.5 rounded-full bg-emerald-500" /> 8 doctors available now
          </motion.div>
        </div>
      </section>

      {/* Booking widget */}
      <section className={`${pad} py-20`}>
        <In>
          <div className="rounded-[32px] p-8" style={{ background: C.ink, color: "#fff" }}>
            <AnimatePresence mode="wait">
              {done ? (
                <motion.div key="done" initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} className="flex flex-col items-center py-8 text-center">
                  <motion.span initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ type: "spring" }} className="grid h-16 w-16 place-items-center rounded-full" style={{ background: C.teal }}>
                    <Check className="h-8 w-8" />
                  </motion.span>
                  <div className="mt-4 text-2xl font-extrabold">Appointment confirmed</div>
                  <div className="mt-1 opacity-70">
                    {depts[dept].n} · {days[day]} · {slot} — SMS & WhatsApp reminder sent
                  </div>
                  <button type="button" onClick={() => setDone(false)} className="mt-5 text-sm underline opacity-70">
                    Book another
                  </button>
                </motion.div>
              ) : (
                <motion.div key="form" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                  <div className="text-2xl font-extrabold">Book an appointment in 3 taps</div>
                  <div className="mt-6 text-xs font-bold uppercase tracking-widest opacity-60">1 · Department</div>
                  <div className={`mt-3 grid gap-2 ${compact ? "grid-cols-2" : "grid-cols-6"}`}>
                    {depts.map((d, i) => (
                      <button key={d.n} type="button" onClick={() => setDept(i)} className="flex flex-col items-center gap-2 rounded-2xl p-3 text-xs font-bold transition-colors" style={{ background: dept === i ? C.teal : "rgba(255,255,255,.07)" }}>
                        <d.i className="h-5 w-5" /> {d.n}
                      </button>
                    ))}
                  </div>
                  <div className={`mt-6 grid gap-6 ${compact ? "grid-cols-1" : "grid-cols-2"}`}>
                    <div>
                      <div className="text-xs font-bold uppercase tracking-widest opacity-60">2 · Day</div>
                      <div className="mt-3 flex flex-wrap gap-2">
                        {days.map((d, i) => (
                          <button key={d} type="button" onClick={() => setDay(i)} className="rounded-xl px-4 py-2.5 text-sm font-bold" style={{ background: day === i ? "#fff" : "rgba(255,255,255,.07)", color: day === i ? C.ink : "#fff" }}>
                            {d}
                          </button>
                        ))}
                      </div>
                    </div>
                    <div>
                      <div className="text-xs font-bold uppercase tracking-widest opacity-60">3 · Time</div>
                      <div className="mt-3 flex flex-wrap gap-2">
                        {["9:30", "10:30", "11:30", "4:00", "5:30"].map((t) => (
                          <button key={t} type="button" onClick={() => setSlot(t)} className="flex items-center gap-1.5 rounded-xl px-4 py-2.5 text-sm font-bold" style={{ background: slot === t ? "#fff" : "rgba(255,255,255,.07)", color: slot === t ? C.ink : "#fff" }}>
                            <Clock className="h-3.5 w-3.5" /> {t}
                          </button>
                        ))}
                      </div>
                    </div>
                  </div>
                  <button type="button" onClick={() => setDone(true)} className="mt-8 w-full rounded-2xl py-4 text-sm font-extrabold" style={{ background: C.teal }}>
                    Confirm appointment
                  </button>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </In>
      </section>

      {/* Doctors */}
      <section className={`${pad} pb-20`}>
        <In>
          <h2 className={`font-extrabold tracking-tight ${compact ? "text-3xl" : "text-5xl"}`}>Meet our specialists</h2>
        </In>
        <div className={`mt-10 grid gap-5 ${compact ? "grid-cols-2" : "grid-cols-4"}`}>
          {doctors.map((d, i) => (
            <In key={d.n} delay={i * 0.08}>
              <motion.div whileHover={{ y: -8 }} className="overflow-hidden rounded-3xl" style={{ background: C.card, border: `1px solid ${C.line}` }}>
                <div className="relative grid h-40 place-items-center" style={{ background: `linear-gradient(160deg, ${d.c}33, ${d.c}88)` }}>
                  <span className="grid h-24 w-24 place-items-center rounded-full text-3xl font-extrabold text-white" style={{ background: d.c }}>
                    {d.n.split(" ")[1][0]}
                  </span>
                  <span className="absolute right-3 top-3 flex items-center gap-1 rounded-full bg-white px-2.5 py-1 text-[10px] font-bold">
                    <span className={`h-2 w-2 rounded-full ${d.on ? "bg-emerald-500" : "bg-slate-300"}`} /> {d.on ? "Available" : "Tomorrow"}
                  </span>
                </div>
                <div className="p-5">
                  <div className="font-extrabold">{d.n}</div>
                  <div className="text-sm" style={{ color: C.muted }}>{d.s} · {d.y} yrs</div>
                </div>
              </motion.div>
            </In>
          ))}
        </div>
      </section>

      <footer className={`${pad} flex justify-between py-8 text-xs`} style={{ background: C.mint, color: C.muted }}>
        <span>© 2026 CarePlus Clinic — sample site</span>
        <span>Departments · Privacy · Reports</span>
      </footer>
    </div>
  );
}
