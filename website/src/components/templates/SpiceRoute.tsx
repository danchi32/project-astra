"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Clock, MapPin, Phone, Minus, Plus, Check, Leaf } from "lucide-react";
import { TplFonts, font, In, type TplProps } from "./kit";

const C = { bg: "#120c07", panel: "#1c140d", text: "#f5e9d7", muted: "#b39d80", gold: "#d9a24a", line: "#3a2b1c", red: "#c0392b" };

const menu: Record<string, { n: string; d: string; p: number; veg: boolean }[]> = {
  Starters: [
    { n: "Tandoori broccoli", d: "Cheddar, mustard, smoked yoghurt", p: 420, veg: true },
    { n: "Amritsari fish", d: "Carom batter, mint chutney", p: 560, veg: false },
    { n: "Dahi ke kebab", d: "Hung curd, rose petals, beetroot", p: 380, veg: true },
  ],
  Mains: [
    { n: "Smoked butter chicken", d: "Charcoal-grilled, tomato makhani", p: 640, veg: false },
    { n: "Dal Spice Route", d: "Black lentils, 18 hours on embers", p: 420, veg: true },
    { n: "Laal maas", d: "Rajasthani mutton, mathania chilli", p: 780, veg: false },
  ],
  Desserts: [
    { n: "Saffron kulfi", d: "Pistachio, rose, edible gold", p: 320, veg: true },
    { n: "Gulab jamun brûlée", d: "Caramelised, cardamom cream", p: 340, veg: true },
  ],
  Drinks: [
    { n: "Kokum spritz", d: "Kokum, ginger, soda", p: 260, veg: true },
    { n: "Masala chai", d: "Slow-brewed, house spice", p: 160, veg: true },
  ],
};

/** A plate seen from above, slowly turning, with steam rising off it. */
function Plate({ size }: { size: number }) {
  return (
    <div className="relative" style={{ width: size, height: size }}>
      {[0, 1, 2].map((i) => (
        <motion.svg key={i} viewBox="0 0 40 120" className="absolute left-1/2 top-[-30%] w-10" style={{ marginLeft: (i - 1) * 40 }} animate={{ y: [20, -30], opacity: [0, 0.5, 0] }} transition={{ duration: 3.5, repeat: Infinity, delay: i * 1.1, ease: "easeOut" }}>
          <path d="M20 120 C 5 95, 35 80, 20 60 S 5 25, 20 0" stroke={C.text} strokeWidth="3" fill="none" strokeLinecap="round" />
        </motion.svg>
      ))}
      <motion.div className="absolute inset-0 rounded-full" animate={{ rotate: 360 }} transition={{ duration: 60, repeat: Infinity, ease: "linear" }} style={{ background: "radial-gradient(circle, #f3ece2 0 58%, #e2d6c4 58% 62%, #f3ece2 62% 70%, #2a1d12 70%)", boxShadow: `0 40px 80px -10px #000, 0 0 0 1px ${C.line}` }}>
        <div className="absolute inset-[18%] rounded-full" style={{ background: "radial-gradient(circle at 40% 35%, #f2a541, #c4621d 55%, #7a2e0e)" }} />
        {Array.from({ length: 9 }, (_, i) => (
          <span key={i} className="absolute h-3 w-5 rounded-full" style={{ background: i % 3 ? "#3f7d3a" : "#fff3d6", left: `${50 + 22 * Math.cos(i * 0.7)}%`, top: `${50 + 22 * Math.sin(i * 0.7)}%`, transform: `rotate(${i * 40}deg)` }} />
        ))}
      </motion.div>
    </div>
  );
}

export default function SpiceRoute({ compact }: TplProps) {
  const tabs = Object.keys(menu);
  const [tab, setTab] = useState(tabs[1]);
  const [guests, setGuests] = useState(2);
  const [time, setTime] = useState("8:00 PM");
  const [booked, setBooked] = useState(false);
  const pad = compact ? "px-5" : "px-14";

  return (
    <div style={{ background: C.bg, color: C.text, fontFamily: font.playfair }} className="relative overflow-hidden">
      <TplFonts />
      <header className={`flex items-center ${compact ? "justify-between" : "justify-center gap-16"} ${pad} py-7 text-sm`} style={{ fontFamily: font.manrope }}>
        {!compact && <span style={{ color: C.muted }}>Menu</span>}
        {!compact && <span style={{ color: C.muted }}>Private dining</span>}
        <span className="text-center text-2xl italic" style={{ fontFamily: font.playfair, color: C.gold }}>
          Spice Route
        </span>
        {!compact && <span style={{ color: C.muted }}>Events</span>}
        <span className="rounded-full px-4 py-2 font-semibold" style={{ border: `1px solid ${C.gold}`, color: C.gold }}>
          Reserve
        </span>
      </header>

      {/* Hero */}
      <section className={`relative ${pad} ${compact ? "pb-14 pt-6 text-center" : "grid grid-cols-2 items-center gap-10 pb-24 pt-10"}`}>
        <div className="pointer-events-none absolute left-1/2 top-1/2 h-[600px] w-[600px] -translate-x-1/2 -translate-y-1/2 rounded-full opacity-20 blur-[120px]" style={{ background: C.gold }} />
        <div className="relative">
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="text-xs uppercase tracking-[0.4em]" style={{ color: C.gold, fontFamily: font.manrope }}>
            Modern Indian kitchen · Est. 2019
          </motion.div>
          <motion.h1 initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 1 }} className={`mt-6 leading-[1.02] ${compact ? "text-5xl" : "text-7xl"}`}>
            Flavours worth <em style={{ color: C.gold }}>travelling</em> for
          </motion.h1>
          <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.4 }} className="mt-6 max-w-md text-lg" style={{ color: C.muted, fontFamily: font.manrope, marginInline: compact ? "auto" : undefined }}>
            Slow-cooked classics and seasonal specials, served in a room made for long dinners.
          </motion.p>
          <div className={`mt-8 flex gap-4 ${compact ? "justify-center" : ""}`} style={{ fontFamily: font.manrope }}>
            <span className="rounded-full px-7 py-3.5 text-sm font-bold" style={{ background: C.gold, color: C.bg }}>
              Book a table
            </span>
            <span className="rounded-full px-7 py-3.5 text-sm font-bold" style={{ border: `1px solid ${C.line}` }}>
              View menu
            </span>
          </div>
        </div>
        <div className={`relative grid place-items-center ${compact ? "mt-14" : ""}`}>
          <Plate size={compact ? 260 : 440} />
        </div>
      </section>

      {/* Quote */}
      <section className={`${pad} py-20 text-center`} style={{ background: C.panel }}>
        <In>
          <p className={`mx-auto max-w-3xl italic leading-snug ${compact ? "text-2xl" : "text-4xl"}`}>
            “Every dish starts with a memory — a grandmother&apos;s kitchen, a roadside dhaba, a festival table.”
          </p>
          <div className="mt-6 text-sm uppercase tracking-[0.3em]" style={{ color: C.gold, fontFamily: font.manrope }}>
            — Chef Arjun Mehra
          </div>
        </In>
      </section>

      {/* Menu with tabs */}
      <section className={`${pad} py-24`}>
        <In className="text-center">
          <div className="text-xs uppercase tracking-[0.4em]" style={{ color: C.gold, fontFamily: font.manrope }}>
            The menu
          </div>
          <h2 className={`mt-3 ${compact ? "text-4xl" : "text-5xl"}`}>Tonight&apos;s table</h2>
        </In>
        <div className="mt-10 flex flex-wrap justify-center gap-2" style={{ fontFamily: font.manrope }}>
          {tabs.map((t) => (
            <button key={t} type="button" onClick={() => setTab(t)} className="relative rounded-full px-5 py-2 text-sm font-semibold">
              {tab === t && <motion.span layoutId="menu-tab" className="absolute inset-0 rounded-full" style={{ background: C.gold }} />}
              <span className="relative" style={{ color: tab === t ? C.bg : C.muted }}>
                {t}
              </span>
            </button>
          ))}
        </div>
        <div className="mx-auto mt-10 max-w-3xl">
          <AnimatePresence mode="wait">
            <motion.div key={tab} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -16 }} transition={{ duration: 0.35 }} className="space-y-7">
              {menu[tab].map((m) => (
                <div key={m.n}>
                  <div className="flex items-baseline gap-3">
                    <span className="grid h-4 w-4 shrink-0 place-items-center border" style={{ borderColor: m.veg ? "#3f9d4a" : C.red }}>
                      <span className="h-2 w-2 rounded-full" style={{ background: m.veg ? "#3f9d4a" : C.red }} />
                    </span>
                    <span className="text-xl">{m.n}</span>
                    <span className="flex-1 border-b border-dotted" style={{ borderColor: C.line }} />
                    <span className="text-xl" style={{ color: C.gold }}>
                      ₹{m.p}
                    </span>
                  </div>
                  <div className="ml-7 mt-1 text-sm" style={{ color: C.muted, fontFamily: font.manrope }}>
                    {m.d}
                  </div>
                </div>
              ))}
            </motion.div>
          </AnimatePresence>
        </div>
      </section>

      {/* Gallery + reservation */}
      <section className={`${pad} pb-24 ${compact ? "space-y-8" : "grid grid-cols-[1.2fr_1fr] gap-10"}`}>
        <div className="grid grid-cols-3 grid-rows-2 gap-3" style={{ height: compact ? 280 : 440 }}>
          {[
            "radial-gradient(circle at 30% 30%, #f2a541, #7a2e0e)",
            "radial-gradient(circle at 60% 40%, #6d8b3a, #1f2a10)",
            "radial-gradient(circle at 50% 50%, #e9d3b1, #8b5e34)",
            "radial-gradient(circle at 40% 60%, #b8322a, #3a0d08)",
            "radial-gradient(circle at 50% 30%, #d9a24a, #3a2b1c)",
          ].map((bg, i) => (
            <In key={i} delay={i * 0.08} className={i === 0 ? "col-span-2 row-span-1" : i === 3 ? "col-span-2" : ""}>
              <div className="h-full rounded-2xl transition-transform duration-500 hover:scale-[1.03]" style={{ background: bg }} />
            </In>
          ))}
        </div>

        <In>
          <div className="rounded-3xl p-8" style={{ background: C.panel, border: `1px solid ${C.line}`, fontFamily: font.manrope }}>
            <AnimatePresence mode="wait">
              {booked ? (
                <motion.div key="ok" initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} className="py-10 text-center">
                  <span className="mx-auto grid h-16 w-16 place-items-center rounded-full" style={{ background: C.gold, color: C.bg }}>
                    <Check className="h-8 w-8" />
                  </span>
                  <div className="mt-5 text-2xl" style={{ fontFamily: font.playfair }}>
                    Table reserved
                  </div>
                  <div className="mt-2 text-sm" style={{ color: C.muted }}>
                    {guests} guests · Friday · {time}
                  </div>
                  <button type="button" onClick={() => setBooked(false)} className="mt-6 text-xs underline" style={{ color: C.muted }}>
                    Change booking
                  </button>
                </motion.div>
              ) : (
                <motion.div key="form" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                  <div className="text-2xl" style={{ fontFamily: font.playfair }}>
                    Reserve a table
                  </div>
                  <div className="mt-6 text-xs uppercase tracking-widest" style={{ color: C.muted }}>
                    Guests
                  </div>
                  <div className="mt-2 flex items-center gap-4">
                    <button type="button" onClick={() => setGuests((g) => Math.max(1, g - 1))} className="grid h-10 w-10 place-items-center rounded-full" style={{ border: `1px solid ${C.line}` }} aria-label="Fewer guests">
                      <Minus className="h-4 w-4" />
                    </button>
                    <motion.span key={guests} initial={{ scale: 0.6 }} animate={{ scale: 1 }} className="w-8 text-center text-2xl font-bold">
                      {guests}
                    </motion.span>
                    <button type="button" onClick={() => setGuests((g) => Math.min(12, g + 1))} className="grid h-10 w-10 place-items-center rounded-full" style={{ border: `1px solid ${C.line}` }} aria-label="More guests">
                      <Plus className="h-4 w-4" />
                    </button>
                  </div>
                  <div className="mt-6 text-xs uppercase tracking-widest" style={{ color: C.muted }}>
                    Friday, time
                  </div>
                  <div className="mt-2 grid grid-cols-3 gap-2">
                    {["7:00 PM", "7:30 PM", "8:00 PM", "8:30 PM", "9:00 PM", "9:30 PM"].map((t) => (
                      <button key={t} type="button" onClick={() => setTime(t)} className="rounded-xl py-2.5 text-sm font-semibold transition-colors" style={{ background: time === t ? C.gold : "transparent", color: time === t ? C.bg : C.text, border: `1px solid ${time === t ? C.gold : C.line}` }}>
                        {t}
                      </button>
                    ))}
                  </div>
                  <button type="button" onClick={() => setBooked(true)} className="mt-7 w-full rounded-full py-4 text-sm font-bold" style={{ background: C.gold, color: C.bg }}>
                    Confirm reservation
                  </button>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </In>
      </section>

      <footer className={`${pad} grid gap-6 border-t py-12 text-sm ${compact ? "grid-cols-1" : "grid-cols-3"}`} style={{ borderColor: C.line, color: C.muted, fontFamily: font.manrope }}>
        <span className="flex items-center gap-2"><Clock className="h-4 w-4" style={{ color: C.gold }} /> Open daily · 12 pm – 11:30 pm</span>
        <span className="flex items-center gap-2"><MapPin className="h-4 w-4" style={{ color: C.gold }} /> 14 Market Road, Sector 18</span>
        <span className="flex items-center gap-2"><Phone className="h-4 w-4" style={{ color: C.gold }} /> +91 00000 00000 · <Leaf className="h-4 w-4" /> Sample site</span>
      </footer>
    </div>
  );
}
