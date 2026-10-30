"use client";

import { motion } from "framer-motion";
import { BookOpen, FlaskConical, Calculator, Palette, Trophy, Users, Laptop, Bus, Star, ArrowRight } from "lucide-react";
import { TplFonts, font, In, type TplProps } from "./kit";

const C = { bg: "#fffaf0", ink: "#231942", muted: "#6b6489", purple: "#7b2ff7", pink: "#ff4f8b", yellow: "#ffc93c", green: "#2ec4b6", blue: "#3a86ff" };

const shapes = [
  { c: C.yellow, s: 70, x: "6%", y: "18%", r: "50%", d: 5 },
  { c: C.pink, s: 46, x: "88%", y: "14%", r: "12px", d: 6 },
  { c: C.green, s: 58, x: "80%", y: "62%", r: "50% 50% 0 50%", d: 7 },
  { c: C.blue, s: 36, x: "12%", y: "70%", r: "8px", d: 4.5 },
  { c: C.purple, s: 28, x: "50%", y: "8%", r: "50%", d: 5.5 },
];

const courses = [
  { t: "Little Explorers", a: "Ages 3–6", d: "Play-based learning, phonics and numbers.", c: C.yellow, i: Palette },
  { t: "Foundation", a: "Class 1–5", d: "Strong basics in reading, maths and science.", c: C.green, i: BookOpen },
  { t: "Middle School", a: "Class 6–8", d: "Olympiad prep, coding and projects.", c: C.blue, i: Calculator },
  { t: "Senior Secondary", a: "Class 9–12", d: "Board excellence with JEE / NEET foundation.", c: C.pink, i: FlaskConical },
];

export default function BrightMinds({ compact }: TplProps) {
  const pad = compact ? "px-5" : "px-14";

  return (
    <div style={{ background: C.bg, color: C.ink, fontFamily: font.fredoka }} className="relative overflow-hidden">
      <TplFonts />
      <header className={`relative z-10 flex items-center justify-between ${pad} py-6`}>
        <span className="flex items-center gap-2 text-2xl font-bold">
          <motion.span animate={{ rotate: [0, 15, -10, 0] }} transition={{ duration: 3, repeat: Infinity }} className="grid h-11 w-11 place-items-center rounded-2xl text-white" style={{ background: C.purple }}>
            <Star className="h-6 w-6" fill="#fff" />
          </motion.span>
          BrightMinds
        </span>
        {!compact && (
          <nav className="flex gap-7 text-base font-medium" style={{ color: C.muted }}>
            {["Programs", "Admissions", "Campus", "Results", "Parents"].map((n) => (
              <span key={n}>{n}</span>
            ))}
          </nav>
        )}
        <span className="rounded-full px-5 py-2.5 text-base font-semibold text-white" style={{ background: C.pink }}>
          Apply now
        </span>
      </header>

      {/* Hero */}
      <section className={`relative ${pad} pb-24 pt-16 text-center`}>
        {shapes.map((s, i) => (
          <motion.span
            key={i}
            className="pointer-events-none absolute"
            style={{ left: s.x, top: s.y, width: s.s, height: s.s, background: s.c, borderRadius: s.r, opacity: 0.85 }}
            animate={{ y: [0, -24, 0], rotate: [0, 25, 0] }}
            transition={{ duration: s.d, repeat: Infinity, ease: "easeInOut" }}
          />
        ))}
        <motion.svg className="pointer-events-none absolute left-[22%] top-[58%] w-28" viewBox="0 0 120 30" initial={{ pathLength: 0 }}>
          <motion.path d="M5 15 Q 20 0 35 15 T 65 15 T 95 15 T 115 15" fill="none" stroke={C.purple} strokeWidth="5" strokeLinecap="round" initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 1.5, delay: 0.6 }} />
        </motion.svg>

        <motion.div
          className={`absolute ${compact ? "right-3 top-2 h-20 w-20 text-[10px]" : "right-[14%] top-[34%] h-28 w-28 text-xs"} grid place-items-center rounded-full text-center font-bold leading-tight text-white`}
          style={{ background: C.purple }}
          animate={{ rotate: [0, 360] }}
          transition={{ duration: 18, repeat: Infinity, ease: "linear" }}
        >
          ADMISSIONS
          <br />
          OPEN
          <br />
          2026–27
        </motion.div>

        <motion.h1 initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} transition={{ type: "spring", stiffness: 120 }} className={`relative mx-auto max-w-4xl font-bold leading-[1.05] ${compact ? "text-5xl" : "text-7xl"}`}>
          Where{" "}
          <span className="relative inline-block">
            <span className="relative z-10">curious</span>
            <motion.span className="absolute inset-x-[-6px] bottom-1 top-1/2 -z-0 rounded-lg" style={{ background: C.yellow }} initial={{ scaleX: 0 }} animate={{ scaleX: 1 }} transition={{ delay: 0.5, duration: 0.6 }} />
          </span>{" "}
          minds become{" "}
          <span style={{ color: C.pink }} className="inline-block -rotate-2">
            confident
          </span>{" "}
          achievers
        </motion.h1>
        <p className="relative mx-auto mt-6 max-w-xl text-xl" style={{ color: C.muted }}>
          Small batches, caring teachers and a learning experience kids actually look forward to.
        </p>
        <div className="relative mt-9 flex flex-wrap justify-center gap-4">
          <motion.span whileHover={{ scale: 1.06, rotate: -2 }} className="inline-flex items-center gap-2 rounded-full px-8 py-4 text-lg font-semibold text-white" style={{ background: C.purple, boxShadow: `0 8px 0 ${C.ink}` }}>
            Book a campus visit <ArrowRight className="h-5 w-5" />
          </motion.span>
          <motion.span whileHover={{ scale: 1.06, rotate: 2 }} className="rounded-full px-8 py-4 text-lg font-semibold" style={{ background: "#fff", border: `3px solid ${C.ink}`, boxShadow: `0 8px 0 ${C.ink}` }}>
            Explore programs
          </motion.span>
        </div>
      </section>

      {/* Courses */}
      <section className={`${pad} pb-20`}>
        <In className="text-center">
          <h2 className={`font-bold ${compact ? "text-4xl" : "text-5xl"}`}>Programs for every age</h2>
        </In>
        <div className={`mt-12 grid gap-6 ${compact ? "grid-cols-1" : "grid-cols-4"}`}>
          {courses.map((c, i) => (
            <In key={c.t} delay={i * 0.1}>
              <motion.div whileHover={{ rotate: 0, y: -10 }} initial={{ rotate: i % 2 ? 2.5 : -2.5 }} animate={{ rotate: i % 2 ? 2.5 : -2.5 }} className="overflow-hidden rounded-[28px]" style={{ background: "#fff", border: `3px solid ${C.ink}`, boxShadow: `6px 6px 0 ${C.ink}` }}>
                <div className="relative grid h-32 place-items-center" style={{ background: c.c }}>
                  <motion.span animate={{ y: [0, -6, 0] }} transition={{ duration: 2.5, repeat: Infinity, delay: i * 0.3 }}>
                    <c.i className="h-14 w-14" strokeWidth={1.8} />
                  </motion.span>
                </div>
                <div className="p-6">
                  <span className="rounded-full px-3 py-1 text-sm font-semibold" style={{ background: c.c + "55" }}>
                    {c.a}
                  </span>
                  <div className="mt-3 text-2xl font-bold">{c.t}</div>
                  <div className="mt-1" style={{ color: C.muted }}>
                    {c.d}
                  </div>
                </div>
              </motion.div>
            </In>
          ))}
        </div>
      </section>

      {/* Why us */}
      <section className={`${pad} py-20`} style={{ background: C.ink, color: "#fff" }}>
        <div className={`grid gap-8 ${compact ? "grid-cols-2" : "grid-cols-4"}`}>
          {[
            { i: Users, v: "1:15", l: "Teacher–student ratio", c: C.yellow },
            { i: Trophy, v: "98%", l: "Board results", c: C.pink },
            { i: Laptop, v: "40+", l: "Smart classrooms", c: C.green },
            { i: Bus, v: "25", l: "GPS-tracked buses", c: C.blue },
          ].map((x, i) => (
            <In key={x.l} delay={i * 0.08} className="text-center">
              <motion.span whileHover={{ scale: 1.2, rotate: 10 }} className="mx-auto grid h-16 w-16 place-items-center rounded-2xl" style={{ background: x.c, color: C.ink }}>
                <x.i className="h-8 w-8" />
              </motion.span>
              <div className="mt-4 text-5xl font-bold">{x.v}</div>
              <div className="mt-1 opacity-70">{x.l}</div>
            </In>
          ))}
        </div>
      </section>

      {/* Admission steps */}
      <section className={`${pad} py-20`}>
        <In className="text-center">
          <h2 className={`font-bold ${compact ? "text-4xl" : "text-5xl"}`}>Admission in 3 easy steps</h2>
        </In>
        <div className={`mt-12 grid gap-8 ${compact ? "grid-cols-1" : "grid-cols-3"}`}>
          {["Fill the online form", "Meet us on campus", "Welcome to BrightMinds!"].map((s, i) => (
            <In key={s} delay={i * 0.15} className="text-center">
              <motion.div className="mx-auto grid h-20 w-20 place-items-center rounded-full text-3xl font-bold text-white" style={{ background: [C.purple, C.pink, C.green][i] }} animate={{ y: [0, -8, 0] }} transition={{ duration: 2, repeat: Infinity, delay: i * 0.4 }}>
                {i + 1}
              </motion.div>
              <div className="mt-4 text-2xl font-bold">{s}</div>
            </In>
          ))}
        </div>
      </section>

      {/* Polaroid gallery */}
      <section className={`${pad} pb-24`}>
        <div className={`flex flex-wrap justify-center ${compact ? "gap-4" : "gap-8"}`}>
          {[C.yellow, C.blue, C.pink, C.green, C.purple].map((c, i) => (
            <In key={i} delay={i * 0.08}>
              <motion.div whileHover={{ rotate: 0, scale: 1.08, zIndex: 10 }} style={{ rotate: (i - 2) * 5, background: "#fff", boxShadow: "0 15px 30px -10px rgba(35,25,66,.3)" }} className="relative p-3 pb-10">
                <div className={compact ? "h-24 w-24" : "h-40 w-40"} style={{ background: `linear-gradient(135deg, ${c}, ${c}88)` }} />
                <div className="absolute bottom-2 left-0 right-0 text-center text-sm" style={{ color: C.muted }}>
                  {["Sports day", "Science fair", "Annual day", "Art week", "Field trip"][i]}
                </div>
              </motion.div>
            </In>
          ))}
        </div>
      </section>

      <footer className={`${pad} flex justify-between py-8 text-sm`} style={{ background: C.yellow }}>
        <span>© 2026 BrightMinds Academy — sample site</span>
        <span>Admissions · Fees · Contact</span>
      </footer>
    </div>
  );
}
