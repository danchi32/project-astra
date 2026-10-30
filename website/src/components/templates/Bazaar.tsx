"use client";

import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  Search,
  Heart,
  User,
  ShoppingBag,
  X,
  Star,
  Shirt,
  Watch,
  Footprints,
  Baby,
  Sparkles,
  Glasses,
  Headphones,
  Backpack,
  Truck,
  RotateCcw,
  ShieldCheck,
  Plus,
  Minus,
  Zap,
} from "lucide-react";
import { TplFonts, font, In, Loop, type TplProps } from "./kit";

const C = { bg: "#fbf7f2", ink: "#16110b", muted: "#7b6f62", orange: "#ff5a1f", soft: "#ffe9dc", card: "#ffffff", line: "#eee3d6" };

const slides = [
  { tag: "New season", title: "Summer edit is here", sub: "Light fabrics, bold colours — up to 40% off.", bg: "linear-gradient(120deg,#ffd6c2,#ffb38a)", icon: Shirt },
  { tag: "Just dropped", title: "Sneakers that move you", sub: "Cushioned, breathable, made for every day.", bg: "linear-gradient(120deg,#d9e8ff,#a9c8ff)", icon: Footprints },
  { tag: "Gift ideas", title: "Watches from ₹1,499", sub: "Minimal designs, two-year warranty.", bg: "linear-gradient(120deg,#e8ddff,#c7b3ff)", icon: Watch },
];

const cats = [
  { name: "Men", icon: Shirt, bg: "#ffe1d1" },
  { name: "Women", icon: Sparkles, bg: "#ffd9e6" },
  { name: "Kids", icon: Baby, bg: "#dff5e3" },
  { name: "Shoes", icon: Footprints, bg: "#dbe8ff" },
  { name: "Watches", icon: Watch, bg: "#efe2ff" },
  { name: "Eyewear", icon: Glasses, bg: "#fff1c9" },
];

const products = [
  { name: "Linen relaxed shirt", price: 1299, was: 1899, rating: 4.7, icon: Shirt, bg: "#ffe3d3" },
  { name: "Cloud runner sneakers", price: 2499, was: 3299, rating: 4.8, icon: Footprints, bg: "#dce9ff" },
  { name: "Minimal steel watch", price: 2999, was: 3999, rating: 4.9, icon: Watch, bg: "#ece3ff" },
  { name: "Noise-cancel earbuds", price: 1799, was: 2999, rating: 4.6, icon: Headphones, bg: "#dff3e6" },
  { name: "Everyday backpack", price: 1599, was: 2199, rating: 4.7, icon: Backpack, bg: "#fff0c7" },
  { name: "Polarised sunglasses", price: 899, was: 1499, rating: 4.5, icon: Glasses, bg: "#ffdbe7" },
  { name: "Kids cotton set", price: 799, was: 1199, rating: 4.8, icon: Baby, bg: "#e1f4f6" },
  { name: "Glow skincare kit", price: 1199, was: 1699, rating: 4.6, icon: Sparkles, bg: "#ffe6d6" },
];

const inr = (n: number) => "₹" + n.toLocaleString("en-IN");

function Countdown() {
  const [s, setS] = useState(5 * 3600 + 42 * 60 + 17);
  useEffect(() => {
    const id = setInterval(() => setS((x) => (x > 0 ? x - 1 : 0)), 1000);
    return () => clearInterval(id);
  }, []);
  const parts = [Math.floor(s / 3600), Math.floor((s % 3600) / 60), s % 60];
  return (
    <div className="flex items-center gap-1.5">
      {parts.map((p, i) => (
        <span key={i} className="flex items-center gap-1.5">
          <span className="grid h-10 w-11 place-items-center rounded-lg text-lg font-bold text-white" style={{ background: C.ink }}>
            {String(p).padStart(2, "0")}
          </span>
          {i < 2 && <span className="font-bold">:</span>}
        </span>
      ))}
    </div>
  );
}

export default function Bazaar({ compact }: TplProps) {
  const [slide, setSlide] = useState(0);
  const [cart, setCart] = useState<Record<string, number>>({ "Cloud runner sneakers": 1 });
  const [open, setOpen] = useState(false);
  const [liked, setLiked] = useState<string[]>(["Minimal steel watch"]);
  const [toast, setToast] = useState<string | null>(null);
  const count = Object.values(cart).reduce((a, b) => a + b, 0);
  const total = products.reduce((sum, p) => sum + (cart[p.name] ?? 0) * p.price, 0);

  useEffect(() => {
    const id = setInterval(() => setSlide((x) => (x + 1) % slides.length), 3800);
    return () => clearInterval(id);
  }, []);

  const add = (name: string, d = 1) => {
    setCart((c) => {
      const n = Math.max(0, (c[name] ?? 0) + d);
      const next = { ...c, [name]: n };
      if (!n) delete next[name];
      return next;
    });
    if (d > 0) {
      setToast(name);
      setTimeout(() => setToast(null), 1600);
    }
  };

  const S = slides[slide];
  const pad = compact ? "px-4" : "px-10";

  return (
    <div className="relative overflow-hidden" style={{ background: C.bg, color: C.ink, fontFamily: font.outfit }}>
      <TplFonts />
      {/* Announcement */}
      <div className="py-2 text-xs font-medium text-white" style={{ background: C.ink }}>
        <Loop duration={22}>
          {["Free shipping above ₹499", "Use code FEST10 for 10% off", "7-day easy returns", "Cash on delivery available"].map((t) => (
            <span key={t} className="mx-8 flex items-center gap-2 whitespace-nowrap">
              <Zap className="h-3 w-3" style={{ color: C.orange }} /> {t}
            </span>
          ))}
        </Loop>
      </div>

      {/* Header */}
      <header className={`sticky top-0 z-20 flex items-center gap-6 ${pad} py-4 backdrop-blur`} style={{ background: C.bg + "ee", borderBottom: `1px solid ${C.line}` }}>
        <div className="text-2xl font-extrabold tracking-tight">
          bazaar<span style={{ color: C.orange }}>.</span>
        </div>
        {!compact && (
          <nav className="flex gap-6 text-sm font-medium" style={{ color: C.muted }}>
            {["New in", "Men", "Women", "Kids", "Sale"].map((n) => (
              <span key={n} style={n === "Sale" ? { color: C.orange } : undefined}>
                {n}
              </span>
            ))}
          </nav>
        )}
        {!compact && (
          <div className="ml-auto flex w-72 items-center gap-2 rounded-full px-4 py-2.5 text-sm" style={{ background: C.card, border: `1px solid ${C.line}`, color: C.muted }}>
            <Search className="h-4 w-4" /> Search products…
          </div>
        )}
        <div className={`flex items-center gap-4 ${compact ? "ml-auto" : ""}`}>
          {compact && <Search className="h-5 w-5" />}
          <Heart className="h-5 w-5" />
          {!compact && <User className="h-5 w-5" />}
          <button type="button" onClick={() => setOpen(true)} className="relative" aria-label="Open cart">
            <ShoppingBag className="h-5 w-5" />
            <motion.span
              key={count}
              initial={{ scale: 0.4 }}
              animate={{ scale: 1 }}
              className="absolute -right-2 -top-2 grid h-5 w-5 place-items-center rounded-full text-[10px] font-bold text-white"
              style={{ background: C.orange }}
            >
              {count}
            </motion.span>
          </button>
        </div>
      </header>

      {/* Hero slider */}
      <section className={`${pad} pt-6`}>
        <div className="relative overflow-hidden rounded-[28px]" style={{ height: compact ? 380 : 440 }}>
          <AnimatePresence mode="popLayout">
            <motion.div
              key={slide}
              initial={{ opacity: 0, x: 60 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -60 }}
              transition={{ duration: 0.6, ease: [0.4, 0, 0.2, 1] }}
              className={`absolute inset-0 flex ${compact ? "flex-col justify-end p-7" : "items-center p-14"}`}
              style={{ background: S.bg }}
            >
              <div className={compact ? "relative z-10" : "relative z-10 max-w-md"}>
                <span className="rounded-full bg-white/70 px-3 py-1 text-xs font-semibold">{S.tag}</span>
                <h1 className={`mt-4 font-extrabold leading-[0.95] tracking-tight ${compact ? "text-4xl" : "text-6xl"}`}>{S.title}</h1>
                <p className="mt-4 text-base opacity-80">{S.sub}</p>
                <span className="mt-6 inline-flex items-center gap-2 rounded-full px-6 py-3 text-sm font-semibold text-white" style={{ background: C.ink }}>
                  Shop the collection →
                </span>
              </div>
              <motion.div
                className={`absolute grid place-items-center rounded-full bg-white/50 ${compact ? "right-[-40px] top-[-30px] h-60 w-60" : "right-20 top-1/2 h-80 w-80 -translate-y-1/2"}`}
                animate={{ rotate: [0, 6, 0, -6, 0], y: [0, -10, 0] }}
                transition={{ duration: 6, repeat: Infinity }}
              >
                <S.icon className={compact ? "h-24 w-24" : "h-36 w-36"} strokeWidth={1.2} />
                <span className="absolute right-6 top-8 rounded-full px-3 py-1.5 text-sm font-bold text-white" style={{ background: C.orange }}>
                  −40%
                </span>
              </motion.div>
            </motion.div>
          </AnimatePresence>
          <div className="absolute bottom-5 right-6 z-10 flex gap-2">
            {slides.map((_, i) => (
              <button key={i} type="button" onClick={() => setSlide(i)} aria-label={`Slide ${i + 1}`} className="h-2 rounded-full transition-all" style={{ width: i === slide ? 28 : 8, background: C.ink }} />
            ))}
          </div>
        </div>
      </section>

      {/* Categories */}
      <section className={`${pad} py-12`}>
        <div className={`grid gap-4 ${compact ? "grid-cols-3" : "grid-cols-6"}`}>
          {cats.map((c, i) => (
            <In key={c.name} delay={i * 0.05} className="group flex flex-col items-center gap-3">
              <div className="grid h-24 w-24 place-items-center rounded-full transition-transform duration-300 group-hover:scale-110 group-hover:-rotate-6" style={{ background: c.bg }}>
                <c.icon className="h-9 w-9" strokeWidth={1.5} />
              </div>
              <span className="text-sm font-semibold">{c.name}</span>
            </In>
          ))}
        </div>
      </section>

      {/* Flash sale */}
      <section className={pad}>
        <div className={`flex ${compact ? "flex-col items-start" : "items-center justify-between"} gap-4 rounded-3xl p-7`} style={{ background: C.soft }}>
          <div>
            <div className="flex items-center gap-2 text-sm font-bold" style={{ color: C.orange }}>
              <Zap className="h-4 w-4" /> FLASH SALE
            </div>
            <div className="mt-1 text-2xl font-extrabold">Deals end in</div>
          </div>
          <Countdown />
        </div>
      </section>

      {/* Products */}
      <section className={`${pad} py-12`}>
        <div className="flex items-end justify-between">
          <h2 className="text-3xl font-extrabold tracking-tight">Trending now</h2>
          <span className="text-sm font-semibold underline">View all</span>
        </div>
        <div className={`mt-7 grid gap-5 ${compact ? "grid-cols-2" : "grid-cols-4"}`}>
          {products.map((p, i) => {
            const fav = liked.includes(p.name);
            return (
              <In key={p.name} delay={(i % 4) * 0.06} className="group">
                <div className="relative overflow-hidden rounded-2xl" style={{ background: p.bg, aspectRatio: "4/5" }}>
                  <span className="absolute left-3 top-3 z-10 rounded-full px-2 py-1 text-[11px] font-bold text-white" style={{ background: C.orange }}>
                    −{Math.round((1 - p.price / p.was) * 100)}%
                  </span>
                  <button
                    type="button"
                    aria-label="Wishlist"
                    onClick={() => setLiked((l) => (fav ? l.filter((x) => x !== p.name) : [...l, p.name]))}
                    className="absolute right-3 top-3 z-10 grid h-8 w-8 place-items-center rounded-full bg-white"
                  >
                    <Heart className="h-4 w-4" style={{ color: fav ? C.orange : C.ink }} fill={fav ? C.orange : "none"} />
                  </button>
                  <div className="absolute inset-0 grid place-items-center transition-transform duration-500 group-hover:scale-110 group-hover:rotate-3">
                    <p.icon className={compact ? "h-16 w-16" : "h-24 w-24"} strokeWidth={1.1} />
                  </div>
                  <button
                    type="button"
                    onClick={() => add(p.name)}
                    className={`absolute inset-x-3 bottom-3 rounded-xl py-2.5 text-sm font-semibold text-white transition-all duration-300 ${compact ? "" : "translate-y-14 group-hover:translate-y-0"}`}
                    style={{ background: C.ink }}
                  >
                    Add to cart
                  </button>
                </div>
                <div className="mt-3 flex items-center gap-1 text-xs" style={{ color: C.muted }}>
                  <Star className="h-3.5 w-3.5" fill="#f5b301" stroke="#f5b301" /> {p.rating}
                </div>
                <div className="mt-1 text-sm font-semibold">{p.name}</div>
                <div className="mt-1 flex items-baseline gap-2">
                  <span className="font-bold">{inr(p.price)}</span>
                  <span className="text-xs line-through" style={{ color: C.muted }}>
                    {inr(p.was)}
                  </span>
                </div>
              </In>
            );
          })}
        </div>
      </section>

      {/* Promo banners */}
      <section className={`${pad} grid gap-5 ${compact ? "grid-cols-1" : "grid-cols-2"}`}>
        {[
          { t: "Buy 2, get 1 free", s: "On all t-shirts this week", bg: C.ink, fg: "#fff" },
          { t: "Student offer", s: "Extra 15% with your college ID", bg: C.orange, fg: "#fff" },
        ].map((b, i) => (
          <In key={b.t} delay={i * 0.1}>
            <div className="relative overflow-hidden rounded-3xl p-9" style={{ background: b.bg, color: b.fg }}>
              <motion.div className="absolute -right-10 -top-10 h-40 w-40 rounded-full bg-white/10" animate={{ scale: [1, 1.25, 1] }} transition={{ duration: 4, repeat: Infinity }} />
              <div className="text-3xl font-extrabold">{b.t}</div>
              <div className="mt-2 opacity-80">{b.s}</div>
              <span className="mt-6 inline-block rounded-full bg-white px-5 py-2.5 text-sm font-semibold" style={{ color: C.ink }}>
                Shop now
              </span>
            </div>
          </In>
        ))}
      </section>

      {/* Trust */}
      <section className={`${pad} grid gap-4 py-14 ${compact ? "grid-cols-1" : "grid-cols-3"}`}>
        {[
          { i: Truck, t: "Fast delivery", s: "Dispatched within 24 hours" },
          { i: RotateCcw, t: "Easy returns", s: "7-day no-questions return" },
          { i: ShieldCheck, t: "Secure checkout", s: "UPI, cards, wallets & COD" },
        ].map((x) => (
          <div key={x.t} className="flex items-center gap-4 rounded-2xl p-5" style={{ background: C.card, border: `1px solid ${C.line}` }}>
            <span className="grid h-12 w-12 place-items-center rounded-xl" style={{ background: C.soft, color: C.orange }}>
              <x.i className="h-6 w-6" />
            </span>
            <div>
              <div className="font-bold">{x.t}</div>
              <div className="text-sm" style={{ color: C.muted }}>
                {x.s}
              </div>
            </div>
          </div>
        ))}
      </section>

      {/* Newsletter + footer */}
      <footer className={`${pad} pb-10`}>
        <div className={`flex ${compact ? "flex-col" : "items-center justify-between"} gap-5 rounded-3xl p-10 text-white`} style={{ background: C.ink }}>
          <div>
            <div className="text-3xl font-extrabold">Get 10% off your first order</div>
            <div className="mt-1 text-sm opacity-70">Join 50,000 shoppers getting early access to sales.</div>
          </div>
          <div className="flex overflow-hidden rounded-full bg-white p-1">
            <span className="px-4 py-2.5 text-sm" style={{ color: C.muted }}>
              your@email.com
            </span>
            <span className="rounded-full px-5 py-2.5 text-sm font-semibold text-white" style={{ background: C.orange }}>
              Subscribe
            </span>
          </div>
        </div>
        <div className="mt-8 flex justify-between text-xs" style={{ color: C.muted }}>
          <span>© 2026 bazaar. Sample store.</span>
          <span>Privacy · Terms · Shipping</span>
        </div>
      </footer>

      {/* Added toast */}
      <AnimatePresence>
        {toast && (
          <motion.div
            initial={{ y: 40, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 40, opacity: 0 }}
            className="fixed bottom-6 left-1/2 z-50 -translate-x-1/2 rounded-full px-5 py-3 text-sm font-semibold text-white shadow-xl"
            style={{ background: C.ink }}
          >
            ✓ {toast} added to cart
          </motion.div>
        )}
      </AnimatePresence>

      {/* Cart drawer */}
      <AnimatePresence>
        {open && (
          <>
            <motion.div className="fixed inset-0 z-30 bg-black/40" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={() => setOpen(false)} />
            <motion.aside
              initial={{ x: "100%" }}
              animate={{ x: 0 }}
              exit={{ x: "100%" }}
              transition={{ type: "spring", stiffness: 260, damping: 30 }}
              className="fixed right-0 top-0 z-40 flex h-full flex-col p-6"
              style={{ width: compact ? "90%" : 400, background: C.card }}
            >
              <div className="flex items-center justify-between">
                <div className="text-xl font-extrabold">Your cart ({count})</div>
                <button type="button" onClick={() => setOpen(false)} aria-label="Close cart">
                  <X className="h-5 w-5" />
                </button>
              </div>
              <div className="mt-6 flex-1 space-y-4 overflow-auto">
                {products
                  .filter((p) => cart[p.name])
                  .map((p) => (
                    <div key={p.name} className="flex items-center gap-3">
                      <span className="grid h-16 w-16 shrink-0 place-items-center rounded-xl" style={{ background: p.bg }}>
                        <p.icon className="h-7 w-7" />
                      </span>
                      <div className="flex-1">
                        <div className="text-sm font-semibold">{p.name}</div>
                        <div className="text-sm font-bold">{inr(p.price)}</div>
                      </div>
                      <div className="flex items-center gap-2 rounded-full px-2 py-1" style={{ border: `1px solid ${C.line}` }}>
                        <button type="button" onClick={() => add(p.name, -1)} aria-label="Less">
                          <Minus className="h-3.5 w-3.5" />
                        </button>
                        <span className="text-sm font-semibold">{cart[p.name]}</span>
                        <button type="button" onClick={() => add(p.name, 1)} aria-label="More">
                          <Plus className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </div>
                  ))}
                {!count && <div className="text-sm" style={{ color: C.muted }}>Your cart is empty.</div>}
              </div>
              <div className="border-t pt-4" style={{ borderColor: C.line }}>
                <div className="flex justify-between font-bold">
                  <span>Subtotal</span>
                  <span>{inr(total)}</span>
                </div>
                <div className="mt-4 rounded-full py-3.5 text-center text-sm font-semibold text-white" style={{ background: C.orange }}>
                  Checkout securely →
                </div>
              </div>
            </motion.aside>
          </>
        )}
      </AnimatePresence>
    </div>
  );
}
