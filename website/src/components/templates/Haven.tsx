"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Search, MapPin, BedDouble, Bath, Maximize, Heart, Phone } from "lucide-react";
import { TplFonts, font, In, type TplProps } from "./kit";

const C = { bg: "#f4efe6", ink: "#14231c", muted: "#62705f", green: "#1f4d3a", gold: "#c7923e", card: "#fffdf8", line: "#e3dccd" };

const listings = [
  { t: "Lake View Residences", type: "Apartments", loc: "Sector 150, Noida", p: "₹1.2 Cr", beds: 3, baths: 3, area: "1,650", bg: "linear-gradient(160deg,#9fc3b0,#2f6b52)" },
  { t: "The Garden Villa", type: "Villas", loc: "Golf Course Rd, Gurugram", p: "₹3.4 Cr", beds: 4, baths: 5, area: "3,200", bg: "linear-gradient(160deg,#e7c89a,#a5672e)" },
  { t: "Skyline Smart Homes", type: "Apartments", loc: "Greater Noida West", p: "₹68 L", beds: 2, baths: 2, area: "1,050", bg: "linear-gradient(160deg,#b9c7e8,#3d5a99)" },
  { t: "Green Acres Plots", type: "Plots", loc: "Yamuna Expressway", p: "₹45 L", beds: 0, baths: 0, area: "2,400", bg: "linear-gradient(160deg,#cfe0a8,#5d7d2b)" },
  { t: "Riverside Penthouse", type: "Apartments", loc: "Sector 128, Noida", p: "₹4.1 Cr", beds: 5, baths: 5, area: "4,800", bg: "linear-gradient(160deg,#d7b7d9,#6d3e74)" },
  { t: "Palm Court Villas", type: "Villas", loc: "Sohna Road", p: "₹2.2 Cr", beds: 4, baths: 4, area: "2,750", bg: "linear-gradient(160deg,#f2d0a4,#b8572f)" },
];

/** Buildings that rise into place, windows that light up one by one. */
function Skyline({ h }: { h: number }) {
  const blds = [
    { w: 70, hh: 0.55 }, { w: 90, hh: 0.8 }, { w: 60, hh: 0.45 }, { w: 110, hh: 1 }, { w: 80, hh: 0.68 }, { w: 64, hh: 0.5 }, { w: 96, hh: 0.86 },
  ];
  return (
    <div className="relative flex items-end justify-center gap-2" style={{ height: h }}>
      <motion.div className="absolute right-[12%] top-[6%] h-24 w-24 rounded-full" style={{ background: C.gold }} animate={{ y: [8, -4, 8] }} transition={{ duration: 6, repeat: Infinity }} />
      {blds.map((b, i) => (
        <motion.div
          key={i}
          className="relative origin-bottom overflow-hidden rounded-t-lg"
          style={{ width: b.w, height: h * 0.85 * b.hh, background: i % 2 ? C.green : "#2c6a50" }}
          initial={{ scaleY: 0 }}
          animate={{ scaleY: 1 }}
          transition={{ duration: 1, delay: 0.2 + i * 0.12, ease: [0.16, 1, 0.3, 1] }}
        >
          <div className="grid grid-cols-3 gap-1.5 p-2.5">
            {Array.from({ length: Math.floor(b.hh * 24) }, (_, j) => (
              <motion.span
                key={j}
                className="h-2.5 rounded-[2px]"
                style={{ background: "#f7d58a" }}
                initial={{ opacity: 0.15 }}
                animate={{ opacity: [0.15, (i + j) % 3 ? 0.9 : 0.2, 0.15] }}
                transition={{ duration: 3 + ((i * 7 + j) % 4), repeat: Infinity, delay: 1 + ((i + j) % 6) * 0.4 }}
              />
            ))}
          </div>
        </motion.div>
      ))}
      <div className="absolute inset-x-0 bottom-0 h-2 rounded" style={{ background: C.ink }} />
    </div>
  );
}

function Emi({ compact }: { compact?: boolean }) {
  const [amt, setAmt] = useState(80);
  const [rate, setRate] = useState(8.5);
  const [yrs, setYrs] = useState(20);
  const P = amt * 100000;
  const r = rate / 1200;
  const n = yrs * 12;
  const emi = (P * r * (1 + r) ** n) / ((1 + r) ** n - 1);
  const interest = emi * n - P;
  const share = P / (P + interest);
  const L = (v: number) => "₹" + Math.round(v).toLocaleString("en-IN");
  const slider = (label: string, val: string, min: number, max: number, step: number, v: number, set: (n: number) => void) => (
    <label className="block">
      <div className="flex justify-between text-sm">
        <span style={{ color: C.muted }}>{label}</span>
        <span className="font-bold">{val}</span>
      </div>
      <input type="range" min={min} max={max} step={step} value={v} onChange={(e) => set(Number(e.target.value))} className="mt-2 w-full" style={{ accentColor: C.green }} />
    </label>
  );
  return (
    <div className={`grid items-center gap-8 ${compact ? "grid-cols-1" : "grid-cols-[1fr_auto]"}`}>
      <div className="space-y-5">
        {slider("Loan amount", `₹${amt} L`, 10, 300, 5, amt, setAmt)}
        {slider("Interest rate", `${rate}%`, 6, 14, 0.1, rate, setRate)}
        {slider("Tenure", `${yrs} years`, 5, 30, 1, yrs, setYrs)}
      </div>
      <div className="text-center">
        <div className="relative mx-auto grid h-40 w-40 place-items-center rounded-full transition-all" style={{ background: `conic-gradient(${C.green} 0 ${share * 360}deg, ${C.gold} 0)` }}>
          <div className="grid h-28 w-28 place-items-center rounded-full" style={{ background: C.card }}>
            <div>
              <div className="text-[10px] uppercase" style={{ color: C.muted }}>
                Monthly EMI
              </div>
              <div className="text-lg font-bold">{L(emi)}</div>
            </div>
          </div>
        </div>
        <div className="mt-3 space-y-1 text-xs">
          <div className="flex items-center gap-2"><span className="h-2 w-2 rounded-full" style={{ background: C.green }} /> Principal {L(P)}</div>
          <div className="flex items-center gap-2"><span className="h-2 w-2 rounded-full" style={{ background: C.gold }} /> Interest {L(interest)}</div>
        </div>
      </div>
    </div>
  );
}

export default function Haven({ compact }: TplProps) {
  const [mode, setMode] = useState("Buy");
  const [type, setType] = useState("All");
  const [liked, setLiked] = useState<string[]>([]);
  const shown = listings.filter((l) => type === "All" || l.type === type);
  const pad = compact ? "px-5" : "px-14";

  return (
    <div style={{ background: C.bg, color: C.ink, fontFamily: font.manrope }} className="overflow-hidden">
      <TplFonts />
      <header className={`flex items-center justify-between ${pad} py-6`}>
        <span className="text-2xl" style={{ fontFamily: font.dmserif }}>
          Haven<span style={{ color: C.gold }}>.</span>
        </span>
        {!compact && (
          <nav className="flex gap-8 text-sm font-medium" style={{ color: C.muted }}>
            {["Buy", "Rent", "New projects", "Sell", "Agents"].map((n) => (
              <span key={n}>{n}</span>
            ))}
          </nav>
        )}
        <span className="flex items-center gap-2 rounded-full px-5 py-2.5 text-sm font-bold text-white" style={{ background: C.green }}>
          <Phone className="h-4 w-4" /> {compact ? "Call" : "Talk to an advisor"}
        </span>
      </header>

      {/* Hero */}
      <section className={`${pad} ${compact ? "pt-4" : "grid grid-cols-[1.05fr_1fr] items-end gap-10 pt-8"}`}>
        <div className="pb-6">
          <motion.h1 initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.9 }} className={`leading-[1.02] ${compact ? "text-5xl" : "text-7xl"}`} style={{ fontFamily: font.dmserif }}>
            Find a home that feels like <span style={{ color: C.green, fontStyle: "italic" }}>you.</span>
          </motion.h1>
          <p className="mt-5 max-w-md text-lg" style={{ color: C.muted }}>
            Verified apartments, villas and plots — with site visits arranged within a day.
          </p>

          {/* Search panel */}
          <motion.div initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }} className="mt-8 rounded-3xl p-3 shadow-2xl" style={{ background: C.card, boxShadow: "0 30px 60px -20px rgba(31,77,58,.35)" }}>
            <div className="flex gap-1 p-1">
              {["Buy", "Rent", "Commercial"].map((m) => (
                <button key={m} type="button" onClick={() => setMode(m)} className="relative rounded-full px-4 py-2 text-sm font-semibold">
                  {mode === m && <motion.span layoutId="haven-mode" className="absolute inset-0 rounded-full" style={{ background: C.green }} />}
                  <span className="relative" style={{ color: mode === m ? "#fff" : C.muted }}>
                    {m}
                  </span>
                </button>
              ))}
            </div>
            <div className={`mt-2 grid gap-2 ${compact ? "grid-cols-1" : "grid-cols-[1.3fr_1fr_1fr_auto]"}`}>
              {[
                { l: "Location", v: "Noida, Gurugram…" },
                { l: "Property type", v: "Apartment" },
                { l: "Budget", v: "₹50 L – ₹1.5 Cr" },
              ].map((f) => (
                <div key={f.l} className="rounded-2xl px-4 py-3" style={{ background: C.bg }}>
                  <div className="text-[10px] font-bold uppercase tracking-wider" style={{ color: C.muted }}>
                    {f.l}
                  </div>
                  <div className="text-sm font-semibold">{f.v}</div>
                </div>
              ))}
              <span className="grid place-items-center rounded-2xl px-6 py-3 text-white" style={{ background: C.gold }}>
                <Search className="h-5 w-5" />
              </span>
            </div>
          </motion.div>
        </div>
        <div className={compact ? "mt-10" : ""}>
          <Skyline h={compact ? 260 : 460} />
        </div>
      </section>

      {/* Stats */}
      <section className={`${pad} grid gap-4 py-14 ${compact ? "grid-cols-2" : "grid-cols-4"}`}>
        {[["1,500+", "Homes sold"], ["40+", "Projects"], ["4.9★", "Client rating"], ["24 h", "Site visit"]].map(([v, l], i) => (
          <In key={l} delay={i * 0.06}>
            <div className="text-4xl" style={{ fontFamily: font.dmserif, color: C.green }}>
              {v}
            </div>
            <div className="text-sm" style={{ color: C.muted }}>
              {l}
            </div>
          </In>
        ))}
      </section>

      {/* Listings */}
      <section className={`${pad} pb-20`}>
        <div className={`flex ${compact ? "flex-col gap-4" : "items-end justify-between"}`}>
          <h2 className={compact ? "text-4xl" : "text-5xl"} style={{ fontFamily: font.dmserif }}>
            Featured properties
          </h2>
          <div className="flex flex-wrap gap-2">
            {["All", "Apartments", "Villas", "Plots"].map((t) => (
              <button key={t} type="button" onClick={() => setType(t)} className="rounded-full px-4 py-2 text-sm font-semibold transition-colors" style={{ background: type === t ? C.ink : "transparent", color: type === t ? "#fff" : C.ink, border: `1px solid ${type === t ? C.ink : C.line}` }}>
                {t}
              </button>
            ))}
          </div>
        </div>
        <motion.div layout className={`mt-10 grid gap-6 ${compact ? "grid-cols-1" : "grid-cols-3"}`}>
          <AnimatePresence mode="popLayout">
            {shown.map((l) => {
              const fav = liked.includes(l.t);
              return (
                <motion.div key={l.t} layout initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.95 }} className="group overflow-hidden rounded-3xl" style={{ background: C.card, border: `1px solid ${C.line}` }}>
                  <div className="relative h-52 overflow-hidden">
                    <div className="absolute inset-0 transition-transform duration-700 group-hover:scale-110" style={{ background: l.bg }} />
                    <div className="absolute bottom-0 left-1/2 flex -translate-x-1/2 items-end gap-1.5">
                      {[50, 80, 64].map((hh, i) => (
                        <div key={i} className="w-10 rounded-t-md bg-white/30 backdrop-blur" style={{ height: hh }} />
                      ))}
                    </div>
                    <span className="absolute left-4 top-4 rounded-full bg-white/90 px-3 py-1 text-xs font-bold">For sale</span>
                    <button type="button" aria-label="Save" onClick={() => setLiked((x) => (fav ? x.filter((y) => y !== l.t) : [...x, l.t]))} className="absolute right-4 top-4 grid h-9 w-9 place-items-center rounded-full bg-white/90">
                      <Heart className="h-4 w-4" fill={fav ? "#e0475b" : "none"} stroke={fav ? "#e0475b" : C.ink} />
                    </button>
                  </div>
                  <div className="p-6">
                    <div className="text-2xl" style={{ fontFamily: font.dmserif, color: C.green }}>
                      {l.p}
                    </div>
                    <div className="mt-1 font-bold">{l.t}</div>
                    <div className="mt-1 flex items-center gap-1 text-sm" style={{ color: C.muted }}>
                      <MapPin className="h-3.5 w-3.5" /> {l.loc}
                    </div>
                    <div className="mt-5 flex gap-5 border-t pt-4 text-sm" style={{ borderColor: C.line }}>
                      {l.beds > 0 && <span className="flex items-center gap-1.5"><BedDouble className="h-4 w-4" style={{ color: C.gold }} /> {l.beds} Beds</span>}
                      {l.baths > 0 && <span className="flex items-center gap-1.5"><Bath className="h-4 w-4" style={{ color: C.gold }} /> {l.baths}</span>}
                      <span className="flex items-center gap-1.5"><Maximize className="h-4 w-4" style={{ color: C.gold }} /> {l.area} ft²</span>
                    </div>
                  </div>
                </motion.div>
              );
            })}
          </AnimatePresence>
        </motion.div>
      </section>

      {/* EMI calculator */}
      <section className={`${pad} pb-20`}>
        <In>
          <div className={`rounded-[32px] p-10 ${compact ? "" : "grid grid-cols-[1fr_1.4fr] items-center gap-12"}`} style={{ background: C.card, border: `1px solid ${C.line}` }}>
            <div className={compact ? "mb-8" : ""}>
              <div className="text-xs font-bold uppercase tracking-widest" style={{ color: C.gold }}>
                Plan your purchase
              </div>
              <h2 className="mt-2 text-4xl" style={{ fontFamily: font.dmserif }}>
                Home loan EMI calculator
              </h2>
              <p className="mt-3 text-sm" style={{ color: C.muted }}>
                Move the sliders to see your monthly payment instantly. Our advisors help you get the best rate from leading banks.
              </p>
            </div>
            <Emi compact={compact} />
          </div>
        </In>
      </section>

      <footer className={`${pad} flex justify-between py-8 text-xs`} style={{ background: C.green, color: "#cfe0d6" }}>
        <span>© 2026 Haven Homes — sample site</span>
        <span>Buy · Rent · Sell · Contact</span>
      </footer>
    </div>
  );
}
