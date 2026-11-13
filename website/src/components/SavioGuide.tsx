"use client";

import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import dynamic from "next/dynamic";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowRight, X } from "lucide-react";
import { useContent } from "@/lib/content";
import { trackEvent } from "@/lib/analytics";
import { hasWebGL } from "@/components/three/Hero3D";
import type { BotLive, BotPose } from "@/components/three/SavioBotScene";

const SavioBotScene = dynamic(() => import("@/components/three/SavioBotScene"), { ssr: false });

/*
 * SAVIO, the site's guide: a small 3D robot that lives on every page.
 *
 * It stands on the top edge of a card, positioned in page coordinates, so it scrolls
 * with the content instead of floating over it. The card nearest the middle of the
 * screen is where it wants to be.
 *   - A new card above or below: it puts down a LADDER and climbs down (or up) it,
 *     or shoots a ROPE to a point above and SWINGS across, Spider-Man style; for a
 *     short drop it just hops. Ladder and rope take turns so it stays fresh.
 *   - Same row, or nobody scrolling: it WALKS, waving hello, along its card and on
 *     to the next one, turning round at the end of the row.
 * On each card it points at the card — no popup, the card speaks for itself — then
 * plays a little: sits on the edge, lies down, dances, waves, or hides behind the card
 * and peeks out (over the top or round the side) to say hello, or slips behind it and
 * comes out from behind the next one.
 *
 * All it ever says is hello, and — now and then, at the homepage CTA, near the bottom
 * of any page (but the contact page), or when clicked — "fill the contact form", as a
 * link to it.
 *
 * Where it stops: wherever along the card's top edge its body covers the least text.
 * Before resting it measures the page's actual text lines (and links, buttons, form
 * fields) under each of a few candidate spots and takes the clearest one; it only lies
 * down — its widest pose — where that is clear too. Walking past text is fine; resting
 * on top of it is not.
 *
 * "Behind a card" is a clip: the parts of the robot that overlap the card are cut away
 * (an even-odd polygon with the card as a hole), so the card appears to cover it.
 *
 * Cards: the homepage marks its stops with data-guide="<id>" and the service cards
 * with data-perch. Other pages are not marked: there it stands on whatever looks like
 * a card — a rounded block of a reasonable size inside <main>.
 *
 * On narrow screens and with prefers-reduced-motion it does not travel: it waits
 * docked at the bottom between the WhatsApp and chat buttons. It appears after the
 * homepage logo intro (#tm-intro), never on the website-template demos, and its "×"
 * (on hover) hides it for the rest of the session.
 */

type Stop = { id: string; side: "left" | "right"; pose: BotPose };

const stopDefaults: Stop[] = [
  { id: "hero", side: "left", pose: "laptop" },
  { id: "services", side: "right", pose: "point" },
  { id: "dev", side: "left", pose: "point" },
  { id: "dashboard", side: "left", pose: "point" },
  { id: "console", side: "right", pose: "point" },
  { id: "healing", side: "right", pose: "point" },
  { id: "cta", side: "left", pose: "cheer" },
];

const greetingDefaults = ["Hi! 👋 May I help you?", "May I help you? 🙂", "Hello there! 👋", "Namaste 🙏 May I help you?"];
const CONTACT_ASK = "Need IT help? Fill the contact form";
const CONTACT_YES = "Sure! Fill the contact form"; // after a click on "May I help you?"

type Trick = "peekTop" | "peekSide" | "walkBehind";

/** What it does once it has been on a card a while. Only a wave or an ask is said aloud. */
const chill: { pose: BotPose; say?: string; trick?: Trick; contact?: boolean }[] = [
  { pose: "sit" },
  { pose: "wave", trick: "peekTop" },
  { pose: "lie" },
  { pose: "wave", say: "Hello! 👋" },
  { pose: "wave", trick: "walkBehind" },
  { pose: "dance" },
  { pose: "cheer", say: CONTACT_ASK, contact: true },
  { pose: "wave", trick: "peekSide" },
  { pose: "thumbs" },
];

const OFF_KEY = "savio-guide-off";
const W = 200; // canvas box, desktop — square so it has room to lie down
const H = 200;
const FEET = 0.77; // the robot's feet sit this far down its box
const IDLE_BEFORE_STROLL = 2000; // ms with no scrolling before it moves on by itself
const POINT_FOR = 4500; // ms it points at a card on arrival
const CHILL_FOR = 5000; // ms it sits / lies / dances before strolling on
const WALK_SPEED = 110; // px per second
const SAY_W = 250; // widest speech bubble (the contact ask)
const SPOTS = 9; // candidate resting spots along a card's top edge
const LIE_OK = 900; // px² of covered text it tolerates before it won't lie down

type Perch = { el: Element; stop: Stop; idx: number }; // idx: homepage stop, -1 elsewhere
type Move =
  | { kind: "idle" }
  | { kind: "walk"; from: number; to: number; start: number; dur: number; greet: boolean }
  | { kind: "jump" | "climb"; fx: number; fy: number; start: number; dur: number }
  | { kind: "ladder"; fx: number; fy: number; start: number; dur: number }
  | { kind: "swing"; fx: number; fy: number; start: number; dur: number }
  | { kind: "trick"; type: Trick; start: number; fx: number; fy: number; to: Perch; toF: number; said: boolean };
type Say = { text: string; contact?: boolean; at: number };
type Box = { l: number; t: number; r: number; b: number };
/** Ladder or rope being drawn on the page this frame, in page coordinates. */
type Gear =
  | { kind: "ladder"; x: number; y1: number; y2: number; grow: number }
  | { kind: "rope"; ax: number; ay: number; hx: number; hy: number; grow: number };

const LADDER_GROW = 350; // ms for the ladder to unfold
const ROPE_SHOOT = 280; // ms for the rope to fly up and catch
const HANDS = 0.2; // with arms raised, its hands are this far down its box
const GEAR_FADE = 350; // ms for ladder / rope to fade once it is done with them

const ease = (p: number) => (p < 0.5 ? 2 * p * p : 1 - (-2 * p + 2) ** 2 / 2);
/** 0→1 progress of `now` through [a, b]. */
const seg = (now: number, a: number, b: number) => Math.min(1, Math.max(0, (now - a) / (b - a)));
const overlap = (a: Box, b: Box) => Math.max(0, Math.min(a.r, b.r) - Math.max(a.l, b.l)) * Math.max(0, Math.min(a.b, b.b) - Math.max(a.t, b.t));

/** Card-like blocks on an unmarked page: rounded, reasonably sized, innermost wins. */
function findCards(): Element[] {
  const all = [...document.querySelectorAll("main [class*='rounded-2xl'], main [class*='rounded-3xl'], main [data-perch]")].filter((el) => {
    if (el.closest("#tm-intro, [data-guide-skip]")) return false;
    const r = el.getBoundingClientRect();
    return r.width >= 220 && r.height >= 90 && !!el.querySelector("h1, h2, h3, h4, p");
  });
  return all.filter((el) => !all.some((o) => o !== el && el.contains(o)));
}

/**
 * Everything on the page a visitor reads or clicks, in page coordinates: each line of
 * text (from the text nodes themselves, so a short line doesn't count as its whole
 * paragraph's width), plus links, buttons and form fields.
 */
function readables(): Box[] {
  const out: Box[] = [];
  const sx = window.scrollX;
  const sy = window.scrollY;
  const push = (r: DOMRect) => {
    if (r.width > 0 && r.height > 0) out.push({ l: r.left + sx, t: r.top + sy, r: r.right + sx, b: r.bottom + sy });
  };
  const main = document.querySelector("main") ?? document.body;
  const walker = document.createTreeWalker(main, NodeFilter.SHOW_TEXT, {
    acceptNode: (n) => (n.textContent?.trim() ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT),
  });
  const range = document.createRange();
  for (let n = walker.nextNode(); n; n = walker.nextNode()) {
    range.selectNodeContents(n);
    for (const r of range.getClientRects()) push(r);
  }
  main.querySelectorAll("a, button, input, select, textarea").forEach((el) => push(el.getBoundingClientRect()));
  return out;
}

export function SavioGuide() {
  const { list } = useContent();
  const pathname = usePathname();
  const stops = list<Stop>("home.guide.stops", stopDefaults);
  const greetings = list<string>("home.guide.greetings", greetingDefaults);
  const [ready, setReady] = useState(false);
  const [off, setOff] = useState(false);
  const [docked, setDocked] = useState(false);
  const [placed, setPlaced] = useState(false); // found a card to stand on
  const [say, setSay] = useState<Say | null>(null);
  const [sayBelow, setSayBelow] = useState(false);
  const [sayShift, setSayShift] = useState(0);
  const box = useRef<HTMLDivElement>(null);
  const figure = useRef<HTMLDivElement>(null); // the robot and its shadow — what gets clipped
  const ladderPath = useRef<SVGPathElement>(null);
  const ropePath = useRef<SVGPathElement>(null);
  const webKnot = useRef<SVGGElement>(null);
  const live = useRef<BotLive>({ move: "idle", t: 0, dir: 0, pose: "point", lookRight: true, greet: false, lean: 0 });
  const skip = pathname?.includes("/templates/") ?? false; // client website demos stay clean
  const onContact = pathname?.startsWith("/contact") ?? false;

  // Respect a previous "×", need WebGL, pick docked vs travelling, wait for the intro.
  useEffect(() => {
    try {
      if (sessionStorage.getItem(OFF_KEY) === "1") return setOff(true);
    } catch {
      /* storage blocked: show the guide */
    }
    if (!hasWebGL()) return setOff(true);
    const narrow = window.matchMedia("(max-width: 767px)");
    const still = window.matchMedia("(prefers-reduced-motion: reduce)");
    const setMode = () => setDocked(narrow.matches || still.matches);
    setMode();
    narrow.addEventListener("change", setMode);
    const wait = window.setInterval(() => {
      if (!document.getElementById("tm-intro")) {
        window.clearInterval(wait);
        window.setTimeout(() => setReady(true), 400);
      }
    }, 300);
    return () => {
      window.clearInterval(wait);
      narrow.removeEventListener("change", setMode);
    };
  }, []);

  // The frame loop: pick the card, move between cards, behave, write the robot's state.
  useEffect(() => {
    if (!ready || off || skip) return;
    let raf = 0;
    let cur: Element | null = null;
    let pos = { x: -W, y: 0 };
    let move: Move = { kind: "idle" };
    let lastScroll = performance.now();
    let lastY = window.scrollY;
    let spotF = 0; // where along the card's top edge it stands, 0 = left end, 1 = right end
    let walkDir: 1 | -1 = 1;
    let phase: "point" | "chill" = "point";
    let phaseUntil = 0;
    let pose: BotPose = "point";
    let chillN = Math.floor(Math.random() * chill.length);
    let greetN = 0;
    let nudged = false;
    let perchCache: Perch[] = [];
    let perchAt = 0;
    let textCache: Box[] = [];
    let textAt = 0;
    let clipped = false;
    let travelN = 0; // alternates ladder and rope
    let fading: (Gear & { until: number }) | null = null;

    const speak = (text: string, now: number, contact = false) => {
      if (contact && onContact) return; // already on the contact page
      setSay({ text, contact, at: now });
    };
    const hush = () => setSay((s) => (s?.contact ? s : null)); // a contact ask stays until it times out

    const onScroll = () => {
      lastScroll = performance.now();
    };
    window.addEventListener("scroll", onScroll, { passive: true });

    // Where it can stand on a card: its top edge, between its two ends.
    const ends = (r: DOMRect, docW: number) => ({
      top: r.top + window.scrollY - H * FEET,
      left: Math.min(Math.max(r.left + window.scrollX - 10, 8), docW - W - 8),
      right: Math.min(Math.max(r.right + window.scrollX - W + 10, 8), docW - W - 8),
    });
    const xAt = (e: { left: number; right: number }, f: number) => e.left + (e.right - e.left) * f;

    // The part of its box the robot actually fills, standing or lying, at box (x, y).
    const body = (x: number, y: number, lying = false): Box =>
      lying
        ? { l: x + W * 0.08, t: y + H * 0.45, r: x + W * 0.92, b: y + H * 0.76 }
        : { l: x + W * 0.32, t: y + H * 0.06, r: x + W * 0.68, b: y + H * 0.74 };

    const texts = (now: number) => {
      if (now - textAt > 700 || !textCache.length) {
        textCache = readables();
        textAt = now;
      }
      return textCache;
    };
    const covered = (b: Box, now: number) => texts(now).reduce((sum, t) => sum + overlap(b, t), 0);

    // The clearest spot along a card's top edge, within [lo, hi]: least text under the
    // robot, and among near-equals the one nearest `prefer` (so it still favours the
    // end it was heading for).
    const bestSpot = (el: Element, prefer: number, now: number, lo = 0, hi = 1) => {
      const e = ends(el.getBoundingClientRect(), document.documentElement.clientWidth);
      let best = prefer;
      let bestScore = Infinity;
      for (let i = 0; i < SPOTS; i++) {
        const f = lo + ((hi - lo) * i) / (SPOTS - 1);
        const score = covered(body(xAt(e, f), e.top), now) + Math.abs(f - prefer) * 300;
        if (score < bestScore) {
          bestScore = score;
          best = f;
        }
      }
      return best;
    };

    // Surfaces it can stand on: the homepage's marked stops (and their data-perch
    // children) when the page has them; otherwise whatever looks like a card.
    const perches = (now: number): Perch[] => {
      if (now - perchAt < 700 && perchCache.length) return perchCache;
      perchAt = now;
      const out: Perch[] = [];
      stops.forEach((s, i) => {
        const el = document.querySelector(`[data-guide="${s.id}"]`);
        if (!el) return;
        const kids = el.querySelectorAll("[data-perch]");
        if (kids.length) kids.forEach((k) => out.push({ el: k, stop: s, idx: i }));
        else out.push({ el, stop: s, idx: i });
      });
      if (!out.length) {
        findCards().forEach((el, i) => out.push({ el, idx: -1, stop: { id: `card-${i}`, side: i % 2 ? "right" : "left", pose: "point" } }));
      }
      perchCache = out;
      return out;
    };

    // Hide whatever part of the robot overlaps `card` (the card is a hole in its clip).
    const hideBehind = (card: Element | null) => {
      if (!figure.current) return;
      if (!card) {
        if (clipped) figure.current.style.clipPath = "none";
        clipped = false;
        return;
      }
      const r = card.getBoundingClientRect();
      const x1 = Math.max(-1, r.left + window.scrollX - pos.x);
      const y1 = Math.max(-1, r.top + window.scrollY - pos.y);
      const x2 = Math.min(W + 1, r.right + window.scrollX - pos.x);
      const y2 = Math.min(H + 1, r.bottom + window.scrollY - pos.y);
      figure.current.style.clipPath =
        x2 <= x1 || y2 <= y1
          ? "none"
          : `polygon(evenodd, 0 0, ${W}px 0, ${W}px ${H}px, 0 ${H}px, 0 0, ${x1}px ${y1}px, ${x2}px ${y1}px, ${x2}px ${y2}px, ${x1}px ${y2}px, ${x1}px ${y1}px)`;
      clipped = true;
    };

    const tick = (now: number) => {
      const vh = window.innerHeight;
      const docW = document.documentElement.clientWidth;
      const all = perches(now).filter((p) => p.el.isConnected && p.el.getBoundingClientRect().width > 0);

      // The card whose top edge is nearest the standing line, with room above it. The
      // current card keeps its place on a near-tie, so equal cards in a row don't
      // flicker and an idle stroll can choose its own neighbour.
      const line = vh * 0.42;
      const score = (el: Element) => {
        const t = el.getBoundingClientRect().top;
        return t < 70 || t > vh * 0.82 ? Infinity : Math.abs(t - line);
      };
      // On a tie (a row of equal cards) the one nearest the robot wins, so it goes
      // straight down its own column — and can use a ladder — instead of across.
      const rank = (el: Element) => {
        const r = el.getBoundingClientRect();
        return score(el) + Math.abs(r.left + r.width / 2 + window.scrollX - (pos.x + W / 2)) * 0.02;
      };
      let best = all.reduce<Perch | null>((acc, p) => (!acc || rank(p.el) < rank(acc.el) ? p : acc), null);
      const mine = all.find((p) => p.el === cur) ?? null;
      if (mine && best && (score(mine.el) - score(best.el) < 8 || score(best.el) === Infinity)) best = mine;
      if (!best || score(best.el) === Infinity) best = mine ?? best;
      // Mid-trick it stays put unless the visitor scrolls to another card.
      if (move.kind === "trick" && mine && best !== mine && now - lastScroll > 300) best = mine;
      if (!best) {
        if (box.current) box.current.style.opacity = "0"; // nothing to stand on here
        raf = requestAnimationFrame(tick);
        return;
      }

      // Near the bottom of the page: ask for the contact form (homepage has its CTA stop).
      const nearBottom = window.scrollY + vh >= document.documentElement.scrollHeight - 260;
      if (nearBottom && !nudged && best.idx < 0) {
        nudged = true;
        speak(CONTACT_ASK, now, true);
        pose = "cheer";
        phase = "point";
        phaseUntil = now + 6000;
      }

      // A new card: walk to it on the same row, hop, use a ladder or swing on a rope —
      // landing on its clearest spot — and point at it.
      if (best.el !== cur) {
        const first = !cur;
        const ne = ends(best.el.getBoundingClientRect(), docW);
        cur = best.el;
        setPlaced(true);
        hush();
        hideBehind(null);
        pose = best.stop.pose;
        phase = "point";
        phaseUntil = now + POINT_FOR;
        if (first) speak(greetings[0] ?? "Hi! 👋 May I help you?", now);
        if (best.stop.id === "cta") speak(CONTACT_ASK, now, true);
        if (docked) {
          move = { kind: "walk", from: 0, to: 0, start: now, dur: 900, greet: true };
        } else if (first) {
          spotF = bestSpot(best.el, best.stop.side === "left" ? 0 : 1, now);
          const tx = xAt(ne, spotF);
          pos = { x: -W, y: ne.top };
          move = { kind: "walk", from: -W, to: tx, start: now, dur: Math.max(1200, ((tx + W) / (WALK_SPEED * 2.5)) * 1000), greet: true };
        } else {
          const nearer = Math.abs(ne.left - pos.x) <= Math.abs(ne.right - pos.x) ? 0 : 1;
          spotF = bestSpot(best.el, nearer, now);
          const tx = xAt(ne, spotF);
          const dy = ne.top - pos.y;
          const dist = Math.hypot(tx - pos.x, dy);
          // A ladder only works if it can stand straight on the new card from here.
          const nr = best.el.getBoundingClientRect();
          const cx = pos.x + W / 2;
          const ladderFits = cx > nr.left + window.scrollX + 24 && cx < nr.right + window.scrollX - 24;
          if (Math.abs(dy) < 40) {
            move = { kind: "walk", from: pos.x, to: tx, start: now, dur: Math.max(500, (Math.abs(tx - pos.x) / (WALK_SPEED * 2)) * 1000), greet: false };
          } else if (Math.abs(dy) < 110) {
            move = { kind: dy > 0 ? "jump" : "climb", fx: pos.x, fy: pos.y, start: now, dur: Math.min(1500, Math.max(750, dist * 0.9)) };
          } else if (ladderFits && travelN++ % 2 === 0) {
            move = { kind: "ladder", fx: pos.x, fy: pos.y, start: now, dur: Math.max(700, (Math.abs(dy) / 170) * 1000) };
          } else {
            travelN++;
            move = { kind: "swing", fx: pos.x, fy: pos.y, start: now, dur: Math.min(1500, Math.max(950, dist * 1.1)) };
          }
        }
      }

      const scrolledRecently = now - lastScroll < IDLE_BEFORE_STROLL || Math.abs(window.scrollY - lastY) > 1;
      lastY = window.scrollY;
      const here = all.find((p) => p.el === cur) ?? best;

      // The card next to this one in its row, in the direction it is heading.
      const neighbour = () => {
        const r = cur!.getBoundingClientRect();
        const row = all
          .filter((p) => Math.abs(p.el.getBoundingClientRect().top - r.top) < 12)
          .sort((a, b) => a.el.getBoundingClientRect().left - b.el.getBoundingClientRect().left);
        const i = row.findIndex((p) => p.el === cur);
        return row[i + walkDir] ?? null;
      };

      // Settled on the card: point at it, then play a little, then stroll on.
      if (move.kind === "idle" && now > phaseUntil) {
        if (phase === "point") {
          let c = chill[chillN++ % chill.length];
          if (c.trick && docked) c = chill[0]; // no hiding when docked
          // Lying down is its widest pose: only where that doesn't cover text either.
          if (c.pose === "lie" && (docked || covered(body(pos.x, pos.y, true), now) > LIE_OK)) c = chill[0];
          phase = "chill";
          phaseUntil = now + CHILL_FOR;
          pose = c.pose;
          hush();
          if (c.say) speak(c.say, now, c.contact);
          if (c.trick) {
            // Slip behind this card (or, for walkBehind, behind the next one along).
            const nb = c.trick === "walkBehind" ? neighbour() : null;
            const to = nb ?? here;
            const toF = bestSpot(to.el, nb ? (walkDir === 1 ? 0 : 1) : 1 - spotF, now);
            move = { kind: "trick", type: c.trick, start: now, fx: pos.x, fy: pos.y, to, toF, said: false };
          }
        } else if (!scrolledRecently && !docked) {
          hush();
          const e = ends(cur!.getBoundingClientRect(), docW);
          const nb = neighbour();
          const hello = greetings[greetN++ % greetings.length] ?? "Hi! 👋";
          // The far part of this card, in the walking direction — if there's room to move.
          const lo = walkDir === 1 ? Math.min(1, spotF + 0.35) : 0;
          const hi = walkDir === 1 ? 1 : Math.max(0, spotF - 0.35);
          if (hi > lo && e.right - e.left > 40) {
            // Along this card, saying hello, to its clearest spot further on.
            spotF = bestSpot(cur!, walkDir === 1 ? 1 : 0, now, lo, hi);
            const to = xAt(e, spotF);
            move = { kind: "walk", from: pos.x, to, start: now, dur: Math.max(400, (Math.abs(to - pos.x) / WALK_SPEED) * 1000), greet: true };
            speak(hello, now);
          } else if (nb) {
            // Across to the neighbouring card in the row.
            const be = ends(nb.el.getBoundingClientRect(), docW);
            cur = nb.el;
            spotF = bestSpot(nb.el, walkDir === 1 ? 0 : 1, now);
            const to = xAt(be, spotF);
            move = { kind: "walk", from: pos.x, to, start: now, dur: (Math.abs(to - pos.x) / WALK_SPEED) * 1000, greet: true };
            speak(hello, now);
          } else {
            walkDir = walkDir === 1 ? -1 : 1; // end of the row: turn round
          }
          pose = best.stop.pose;
          phase = "point";
          phaseUntil = now + POINT_FOR;
        } else if (docked) {
          phase = "point";
          phaseUntil = now + POINT_FOR;
          pose = best.stop.pose;
          hush();
        }
      }

      let mode: BotLive["move"] = "idle";
      let mt = 0;
      let dir: -1 | 0 | 1 = 0;
      let greet = false;
      if (docked) {
        // Docked: a few steps in place on arrival, then the same gestures.
        if (move.kind === "walk") {
          mode = now - move.start < move.dur ? "walk" : "idle";
          greet = true;
          if (mode === "idle") move = { kind: "idle" };
        }
        live.current = { move: mode, t: 0, dir: 0, pose: pose === "lie" ? "sit" : pose, lookRight: true, greet, lean: 0 };
        raf = requestAnimationFrame(tick);
        return;
      }

      const ce = ends(cur!.getBoundingClientRect(), docW);
      let behind: Element | null = null;
      let gear: Gear | null = null;
      let lean = 0;
      if (move.kind === "walk") {
        const p = Math.min(1, (now - move.start) / move.dur);
        pos = { x: move.from + (move.to - move.from) * p, y: pos.y + (ce.top - pos.y) * 0.3 };
        mode = "walk";
        dir = move.to >= move.from ? 1 : -1;
        greet = move.greet;
        if (p >= 1) {
          move = { kind: "idle" };
          hush();
          phase = "point";
          phaseUntil = now + POINT_FOR;
        }
      } else if (move.kind === "jump" || move.kind === "climb") {
        const p = Math.min(1, (now - move.start) / move.dur);
        const tx = xAt(ce, spotF);
        const q = ease(p);
        let y = move.fy + (ce.top - move.fy) * q;
        // A jump arcs up before it falls; a climb swings out a little as it rises.
        y -= Math.sin(p * Math.PI) * (move.kind === "jump" ? 140 : 30);
        pos = { x: move.fx + (tx - move.fx) * q, y };
        mode = move.kind;
        mt = p;
        dir = tx > move.fx + 30 ? 1 : tx < move.fx - 30 ? -1 : 0;
        if (p >= 1) {
          move = { kind: "idle" };
          phase = "point";
          phaseUntil = now + POINT_FOR;
        }
      } else if (move.kind === "ladder") {
        // Unfold a ladder from its feet to the new card's top edge, then climb it rung
        // by rung, then walk to its clearest spot on the new card.
        const m = move;
        const t = now - m.start;
        const p = seg(now, m.start + LADDER_GROW, m.start + LADDER_GROW + m.dur);
        pos = { x: m.fx, y: m.fy + (ce.top - m.fy) * p + (p > 0 && p < 1 ? Math.sin(p * Math.PI * 10) * 3 : 0) };
        mode = t < LADDER_GROW ? "idle" : "ladder";
        gear = { kind: "ladder", x: m.fx + W / 2, y1: m.fy + H * FEET, y2: ce.top + H * FEET, grow: seg(now, m.start, m.start + LADDER_GROW) };
        if (p >= 1) {
          fading = { ...gear, until: now + GEAR_FADE };
          gear = null;
          const to = xAt(ce, spotF);
          move = Math.abs(to - pos.x) > 4 ? { kind: "walk", from: pos.x, to, start: now, dur: Math.max(300, (Math.abs(to - pos.x) / WALK_SPEED) * 1000), greet: false } : { kind: "idle" };
          phase = "point";
          phaseUntil = now + POINT_FOR;
        }
      } else if (move.kind === "swing") {
        // Spider-Man: shoot a rope to a point above both cards, swing across on it
        // (hands following a pendulum arc round that point), let go on the new card.
        const m = move;
        const t = now - m.start;
        const hy = H * HANDS;
        const S = { x: m.fx + W / 2, y: m.fy + hy };
        const E = { x: xAt(ce, spotF) + W / 2, y: ce.top + hy };
        const A = { x: (S.x + E.x) / 2, y: Math.min(S.y, E.y) - 170 - Math.abs(S.x - E.x) * 0.12 };
        const aS = Math.atan2(S.x - A.x, S.y - A.y);
        const aE = Math.atan2(E.x - A.x, E.y - A.y);
        const rS = Math.hypot(S.x - A.x, S.y - A.y);
        const rE = Math.hypot(E.x - A.x, E.y - A.y);
        const q = ease(seg(now, m.start + ROPE_SHOOT, m.start + ROPE_SHOOT + m.dur));
        const ang = aS + (aE - aS) * q;
        const rad = rS + (rE - rS) * q;
        const hand = t < ROPE_SHOOT ? S : { x: A.x + rad * Math.sin(ang), y: A.y + rad * Math.cos(ang) };
        pos = { x: hand.x - W / 2, y: hand.y - hy };
        mode = "swing";
        lean = t < ROPE_SHOOT ? 0 : ang;
        dir = E.x >= S.x ? 1 : -1;
        gear = { kind: "rope", ax: A.x, ay: A.y, hx: hand.x, hy: hand.y, grow: seg(now, m.start, m.start + ROPE_SHOOT) };
        if (t >= ROPE_SHOOT + m.dur) {
          fading = { ...gear, until: now + GEAR_FADE };
          gear = null;
          pos = { x: E.x - W / 2, y: ce.top };
          move = { kind: "idle" };
          phase = "point";
          phaseUntil = now + POINT_FOR;
        }
      } else if (move.kind === "trick") {
        // Hide-and-seek with the card. Everything inside the card is clipped away, so
        // sinking below its top edge reads as ducking behind it.
        const m = move;
        const t = now - m.start;
        const r = cur!.getBoundingClientRect();
        const left = r.left + window.scrollX;
        const right = r.right + window.scrollX;
        const top = r.top + window.scrollY;
        const onLeft = spotF < 0.5;
        const hidden = { x: m.fx, y: ce.top + H * 0.9 }; // ducked fully behind the card
        behind = cur;
        let done = false;
        const peekHello = () => {
          if (m.said) return;
          m.said = true;
          speak("Hello! 👋", now);
        };

        if (m.type === "peekTop") {
          // Duck down, wait, pop the head up over the top edge to say hello, climb back.
          const peekY = ce.top + H * 0.34;
          if (t < 450) pos = { x: m.fx, y: m.fy + (hidden.y - m.fy) * ease(seg(now, m.start, m.start + 450)) };
          else if (t < 1000) pos = hidden;
          else if (t < 1400) pos = { x: m.fx, y: hidden.y + (peekY - hidden.y) * ease(seg(now, m.start + 1000, m.start + 1400)) };
          else if (t < 4600) {
            pos = { x: m.fx, y: peekY };
            peekHello();
          } else if (t < 5100) pos = { x: m.fx, y: peekY + (ce.top - peekY) * ease(seg(now, m.start + 4600, m.start + 5100)) };
          else done = true;
          mode = t < 1400 || t >= 4600 ? "walk" : "idle";
          pose = "wave";
        } else if (m.type === "peekSide") {
          // Duck behind the card, then lean out round its side to wave, then climb back.
          const sideX = (onLeft ? left : right) - W / 2;
          const sideY = top + Math.min(r.height * 0.35, 110) - H * 0.5;
          const inX = onLeft ? left + 30 : right - W - 30;
          if (t < 500) pos = { x: m.fx + (inX - m.fx) * ease(seg(now, m.start, m.start + 500)), y: m.fy + (sideY + 60 - m.fy) * ease(seg(now, m.start, m.start + 500)) };
          else if (t < 900) pos = { x: inX, y: sideY + 60 };
          else if (t < 1300) {
            const q = ease(seg(now, m.start + 900, m.start + 1300));
            pos = { x: inX + (sideX - inX) * q, y: sideY + 60 - 60 * q };
          } else if (t < 4300) {
            pos = { x: sideX, y: sideY };
            peekHello();
          } else if (t < 5000) {
            const q = ease(seg(now, m.start + 4300, m.start + 5000));
            pos = { x: sideX + (m.fx - sideX) * q, y: sideY + (ce.top - sideY) * q };
          } else done = true;
          mode = t < 1300 || t >= 4300 ? "walk" : "idle";
          dir = t < 1300 || t >= 4300 ? (onLeft ? 1 : -1) : 0;
          pose = "wave";
        } else {
          // walkBehind: duck down, walk along behind the cards, come up behind the
          // target card's clearest spot, and say hello from there.
          const te = ends(m.to.el.getBoundingClientRect(), docW);
          const tx = xAt(te, m.toF);
          const walkMs = Math.max(900, (Math.abs(tx - m.fx) / WALK_SPEED) * 1000);
          const lowY = te.top + H * 0.9;
          if (t < 450) pos = { x: m.fx, y: m.fy + (hidden.y - m.fy) * ease(seg(now, m.start, m.start + 450)) };
          else if (t < 450 + walkMs) {
            const q = seg(now, m.start + 450, m.start + 450 + walkMs);
            pos = { x: m.fx + (tx - m.fx) * q, y: hidden.y + (lowY - hidden.y) * q };
            dir = tx >= m.fx ? 1 : -1;
          } else if (t < 450 + walkMs + 450) {
            if (cur !== m.to.el) {
              cur = m.to.el;
              spotF = m.toF;
            }
            pos = { x: tx, y: lowY + (te.top - lowY) * ease(seg(now, m.start + 450 + walkMs, m.start + 900 + walkMs)) };
          } else done = true;
          // Behind whichever card it is over right now.
          const cx = pos.x + W / 2;
          behind =
            [here, m.to].find((p) => {
              const b = p.el.getBoundingClientRect();
              return cx >= b.left + window.scrollX && cx <= b.right + window.scrollX;
            })?.el ?? null;
          mode = "walk";
          pose = "wave";
          if (done) {
            cur = m.to.el;
            spotF = m.toF;
            peekHello();
          }
        }

        if (done) {
          move = { kind: "idle" };
          behind = null;
          pose = m.type === "walkBehind" ? "wave" : here.stop.pose;
          phase = "chill"; // next up: stroll on
          phaseUntil = now + (m.type === "walkBehind" ? 3000 : 600);
        }
      } else {
        // Standing: stay glued to its spot while the layout settles (reveals, resizes).
        const tx = xAt(ce, spotF);
        pos = { x: pos.x + (tx - pos.x) * 0.2, y: ce.top };
      }

      live.current = { move: mode, t: mt, dir, pose, lookRight: spotF < 0.5, greet, lean };
      if (box.current) {
        box.current.style.transform = `translate3d(${pos.x}px, ${pos.y}px, 0)`;
        box.current.style.opacity = "1";
      }
      hideBehind(behind);

      // Draw the ladder or rope (or let the last one fade away).
      if (fading && now >= fading.until) fading = null;
      const g = gear ?? fading;
      const alpha = gear ? 1 : fading ? (fading.until - now) / GEAR_FADE : 0;
      if (ladderPath.current) {
        if (g?.kind === "ladder") {
          const yEnd = g.y1 + (g.y2 - g.y1) * g.grow;
          const lo = Math.min(g.y1, yEnd);
          const hi = Math.max(g.y1, yEnd);
          let d = `M${g.x - 13} ${lo}V${hi}M${g.x + 13} ${lo}V${hi}`;
          for (let y = hi - 6; y > lo; y -= 20) d += `M${g.x - 13} ${y}H${g.x + 13}`;
          ladderPath.current.setAttribute("d", d);
          ladderPath.current.style.opacity = String(alpha);
        } else ladderPath.current.style.opacity = "0";
      }
      if (ropePath.current && webKnot.current) {
        if (g?.kind === "rope") {
          const tipX = g.hx + (g.ax - g.hx) * g.grow;
          const tipY = g.hy + (g.ay - g.hy) * g.grow;
          ropePath.current.setAttribute("d", `M${g.hx} ${g.hy}L${tipX} ${tipY}`);
          ropePath.current.style.opacity = String(alpha);
          webKnot.current.setAttribute("transform", `translate(${g.ax} ${g.ay})`);
          webKnot.current.style.opacity = String(g.grow >= 1 ? alpha : 0);
        } else {
          ropePath.current.style.opacity = "0";
          webKnot.current.style.opacity = "0";
        }
      }

      // Speech above the robot, or below when it is near the top of the screen, shifted
      // sideways so it never runs off the page.
      setSayBelow(pos.y - window.scrollY < 120);
      const want = pos.x + W / 2 - SAY_W / 2;
      const shift = Math.min(Math.max(want, 12), docW - SAY_W - 12) - pos.x;
      setSayShift((old) => (Math.abs(old - shift) > 2 ? shift : old));

      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("scroll", onScroll);
    };
  }, [ready, off, skip, docked, stops, greetings, onContact]);

  // A new page: nothing said yet.
  useEffect(() => {
    setSay(null);
    setPlaced(false);
  }, [pathname]);

  // Whatever it said fades after a while — a hello quickly, the contact ask a bit later.
  useEffect(() => {
    if (!say) return;
    const id = window.setTimeout(() => setSay((s) => (s === say ? null : s)), say.contact ? 7000 : 3500);
    return () => window.clearTimeout(id);
  }, [say]);

  if (off || skip || !ready || !placed) return null;

  const close = () => {
    setOff(true);
    try {
      sessionStorage.setItem(OFF_KEY, "1");
    } catch {
      /* fine: hidden for this page view */
    }
  };
  // Clicking the robot: it asks you to get in touch (or, on the contact page, says hi).
  // Clicking the robot, or its "May I help you?": the contact form, one click away.
  const poke = () => setSay(onContact ? { text: "Fill the form below 👇", at: performance.now() } : { text: CONTACT_YES, contact: true, at: performance.now() });

  const speech = (
    <AnimatePresence mode="wait">
      {say && (
        <motion.div
          key={`${say.text}-${say.at}`}
          initial={{ opacity: 0, y: 6, scale: 0.85 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: -4, scale: 0.9 }}
          transition={{ type: "spring", stiffness: 320, damping: 24 }}
          className={`pointer-events-auto absolute ${sayBelow && !docked ? "top-[78%]" : "bottom-[80%]"}`}
          style={docked ? { left: "50%", x: "-50%" } : say.contact ? { left: sayShift } : { left: "50%", x: "-50%" }}
        >
          {say.contact ? (
            <Link
              href="/contact/"
              onClick={() => trackEvent("guide_contact_click", { source: "savio_guide", page: pathname ?? "" })}
              className="flex w-[250px] max-w-[calc(100vw-24px)] items-center justify-between gap-2 rounded-2xl bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white shadow-xl shadow-brand-600/30 transition hover:bg-brand-500"
            >
              {say.text} <ArrowRight className="h-4 w-4 shrink-0" />
            </Link>
          ) : (
            <button type="button" onClick={poke} className="whitespace-nowrap rounded-full border border-token bg-surface px-3 py-1.5 text-xs font-semibold shadow-lg shadow-brand-600/15 transition hover:border-brand-500">
              {say.text}
            </button>
          )}
        </motion.div>
      )}
    </AnimatePresence>
  );

  const robot = (
    <button type="button" onClick={poke} aria-label="SAVIO guide — may I help you?" className="pointer-events-auto absolute inset-0">
      <SavioBotScene live={live} />
    </button>
  );
  const hide = (
    <button
      type="button"
      onClick={close}
      aria-label="Hide the SAVIO guide"
      className="pointer-events-auto absolute right-8 top-6 z-10 grid h-6 w-6 place-items-center rounded-full border border-token bg-surface text-muted-token opacity-0 shadow transition-opacity hover:text-primary-token focus-visible:opacity-100 group-hover:opacity-100"
    >
      <X className="h-3.5 w-3.5" />
    </button>
  );

  if (docked) {
    return (
      <div className="group pointer-events-none fixed bottom-2 left-1/2 z-40 h-[120px] w-[110px] -translate-x-1/2">
        {speech}
        {robot}
        {hide}
      </div>
    );
  }

  // Portalled to <body> and absolutely positioned in page coordinates, so the robot
  // scrolls with the content — it lives on the page rather than floating over it.
  // Position and clip are written only by the frame loop, never by React, so a
  // re-render can't snap it back to where it started.
  return createPortal(
    <>
      {/* Ladder and rope, drawn in page coordinates by the frame loop */}
      <svg className="pointer-events-none absolute left-0 top-0 z-[29] overflow-visible" width={1} height={1} aria-hidden>
        <path ref={ladderPath} fill="none" stroke="#94a3b8" strokeWidth={4} strokeLinecap="round" style={{ opacity: 0, filter: "drop-shadow(0 2px 2px rgba(0,0,0,.2))" }} />
        <path ref={ropePath} fill="none" stroke="#e0f2fe" strokeWidth={2.5} strokeLinecap="round" style={{ opacity: 0, filter: "drop-shadow(0 0 3px #67e8f9)" }} />
        <g ref={webKnot} stroke="#e0f2fe" strokeWidth={1.5} strokeLinecap="round" style={{ opacity: 0, filter: "drop-shadow(0 0 3px #67e8f9)" }}>
          <circle r={4} fill="#e0f2fe" />
          {[0, 60, 120, 180, 240, 300].map((a) => (
            <line key={a} x1={0} y1={0} x2={Math.cos((a * Math.PI) / 180) * 11} y2={Math.sin((a * Math.PI) / 180) * 11} />
          ))}
        </g>
      </svg>
      <div ref={box} className="group pointer-events-none absolute left-0 top-0 z-30 opacity-0" style={{ width: W, height: H }}>
        {speech}
        <div ref={figure} className="absolute inset-0">
          {/* Contact shadow on the card under its feet */}
          <div className="absolute left-1/2 h-3 w-16 -translate-x-1/2 rounded-[50%] bg-black/25 blur-[3px]" style={{ top: `${FEET * 100 - 3}%` }} />
          {robot}
        </div>
        {hide}
      </div>
    </>,
    document.body,
  );
}
