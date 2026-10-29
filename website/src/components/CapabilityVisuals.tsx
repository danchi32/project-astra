"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { motion, useInView } from "framer-motion";
import {
  Bell, BookOpen, CheckCircle2, FileText, Laptop, Lock, Mail, MonitorSmartphone, ShieldAlert, Ticket, User, Wrench,
} from "lucide-react";

/**
 * A small animated scene on top of each capability card, so the card shows what the feature
 * does before anyone reads it. One scene per entry in the SAVIO page's feature list, in the
 * same order (featureDefaults in app/savio/AstraContent.tsx). Every value shown is an example
 * on one imaginary device or fleet — never a statistic about real customers.
 *
 * Scenes only run while their card is on screen.
 */

const loop = (duration: number, delay = 0) => ({ duration, delay, repeat: Infinity, ease: "easeInOut" as const });

function Frame({ children }: { children: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { margin: "-10% 0px" });
  return (
    <div ref={ref} aria-hidden className="relative mb-5 h-28 overflow-hidden rounded-xl border border-token bg-surface-2">
      {inView && children}
    </div>
  );
}

/** Cycles 0..n-1 every `ms`. */
function useTick(n: number, ms: number) {
  const [i, setI] = useState(0);
  useEffect(() => {
    const id = window.setInterval(() => setI((v) => (v + 1) % n), ms);
    return () => window.clearInterval(id);
  }, [n, ms]);
  return i;
}

const Row = ({ children, className = "" }: { children: ReactNode; className?: string }) => (
  <div className={`flex items-center gap-2 rounded-md bg-surface px-2 py-1 text-[10px] ${className}`}>{children}</div>
);

/* 1 — Asset inventory: devices discovered one after another */
function Inventory() {
  const devices = ["DESIGN-WS-07 · Windows 11", "SALES-LT-14 · Dell 5440", "FIN-LT-03 · ThinkPad T14", "HR-WS-02 · HP 800 G9"];
  const n = useTick(devices.length + 1, 900);
  return (
    <div className="space-y-1 p-2.5">
      {devices.slice(0, Math.max(1, n)).map((d, i) => (
        <motion.div key={d} initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }}>
          <Row><Laptop className="h-3 w-3 text-brand-500" />{d}{i === n - 1 && <span className="ml-auto text-emerald-500">new</span>}</Row>
        </motion.div>
      ))}
    </div>
  );
}

/* 2 — Live telemetry: a moving line and breathing bars */
function Telemetry() {
  return (
    <div className="flex h-full items-end gap-3 p-3">
      <svg viewBox="0 0 120 50" className="h-full flex-1">
        <motion.path
          d="M0 35 L15 30 L30 33 L45 18 L60 26 L75 12 L90 22 L105 15 L120 20"
          fill="none" stroke="#3b82f6" strokeWidth="2" strokeLinecap="round"
          initial={{ pathLength: 0 }} animate={{ pathLength: [0, 1] }} transition={loop(2.4)}
        />
      </svg>
      {["CPU", "RAM", "DISK"].map((l, i) => (
        <div key={l} className="flex h-full flex-col items-center justify-end gap-1">
          <motion.div className="w-3 rounded-sm bg-cyan-500" animate={{ height: ["30%", "70%", "45%", "60%"] }} transition={loop(2.2, i * 0.3)} />
          <span className="text-[8px] text-muted-token">{l}</span>
        </div>
      ))}
    </div>
  );
}

/* 3 — Cognitive engine: intent → knowledge → confidence */
function Cognitive() {
  const steps = ["Intent", "Knowledge", "Confidence"];
  const a = useTick(4, 900);
  return (
    <div className="flex h-full flex-col justify-center gap-2 px-3">
      <div className="flex items-center justify-between">
        {steps.map((s, i) => (
          <div key={s} className="flex items-center gap-1">
            <span className={`rounded-full px-2 py-0.5 text-[9px] font-semibold transition-colors ${a > i ? "bg-brand-600 text-white" : "bg-surface text-muted-token"}`}>{s}</span>
            {i < 2 && <span className="h-px w-3" style={{ background: a > i ? "#3b82f6" : "var(--border)" }} />}
          </div>
        ))}
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-surface">
        <motion.div className="h-full bg-gradient-to-r from-brand-600 to-cyan-500" animate={{ width: `${(a / 3) * 92}%` }} />
      </div>
      <p className="text-[9px] text-muted-token">{a === 3 ? "Confidence: high — safe to propose a fix" : "Reasoning over evidence…"}</p>
    </div>
  );
}

/* 4 — Self-healing: broken → fixing → healthy */
function SelfHeal() {
  const s = useTick(3, 1100);
  const state = [
    { c: "bg-red-500", t: "Outlook not responding" },
    { c: "bg-amber-500", t: "Restarting Outlook…" },
    { c: "bg-emerald-500", t: "Healthy · verified" },
  ][s];
  return (
    <div className="flex h-full items-center justify-center gap-3">
      <motion.span key={s} className={`h-10 w-10 rounded-full ${state.c} grid place-items-center text-white`} initial={{ scale: 0.6 }} animate={{ scale: 1 }}>
        {s === 2 ? <CheckCircle2 className="h-5 w-5" /> : s === 1 ? <Wrench className="h-5 w-5" /> : <ShieldAlert className="h-5 w-5" />}
      </motion.span>
      <span className="text-[11px] font-semibold">{state.t}</span>
    </div>
  );
}

/* 5 — Patch management: a rollout progressing across devices */
function Patch() {
  return (
    <div className="space-y-1.5 p-3">
      {["SALES-LT-14", "FIN-LT-03", "HR-WS-02"].map((d, i) => (
        <div key={d} className="flex items-center gap-2 text-[9px]">
          <span className="w-16 truncate text-muted-token">{d}</span>
          <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-surface">
            <motion.div className="h-full rounded-full bg-brand-500" animate={{ width: ["0%", "100%", "100%"] }} transition={loop(3, i * 0.4)} />
          </div>
          <span className="w-12 text-brand-500">updating</span>
        </div>
      ))}
    </div>
  );
}

/* 6 — Secure offboarding: account locked, session ended */
function Offboard() {
  const s = useTick(3, 1100);
  return (
    <div className="flex h-full items-center justify-center gap-3">
      <span className="grid h-10 w-10 place-items-center rounded-full bg-surface"><User className="h-5 w-5 text-secondary-token" /></span>
      <div className="text-[10px]">
        <p className="font-semibold">rahul.k · leaving today</p>
        <p className={s >= 1 ? "text-red-500" : "text-muted-token"}>{s >= 1 ? "Account disabled" : "Active"}</p>
        <p className={s >= 2 ? "text-red-500" : "text-muted-token"}>{s >= 2 ? "Signed out of session" : "Signed in"}</p>
      </div>
      <motion.span animate={{ rotate: s >= 1 ? 0 : -20, scale: s >= 1 ? 1 : 0.8 }}><Lock className={`h-5 w-5 ${s >= 1 ? "text-red-500" : "text-muted-token"}`} /></motion.span>
    </div>
  );
}

/* 7 — Conversational AI: a question and an answer */
function Chat() {
  const s = useTick(3, 1200);
  return (
    <div className="flex h-full flex-col justify-center gap-1.5 px-3 text-[10px]">
      <div className="self-end rounded-lg rounded-br-sm bg-brand-600 px-2 py-1 text-white">My Teams audio isn&apos;t working</div>
      {s === 1 && <div className="flex gap-1 self-start rounded-lg bg-surface px-2 py-1.5">{[0, 1, 2].map((d) => <motion.span key={d} className="h-1 w-1 rounded-full bg-brand-500" animate={{ y: [0, -2, 0] }} transition={loop(0.8, d * 0.15)} />)}</div>}
      {s === 2 && <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="self-start rounded-lg rounded-bl-sm bg-surface px-2 py-1">Fixed — audio service recovered ✓</motion.div>}
    </div>
  );
}

/* 8 — Approval tiers: an action routed to its tier */
function Tiers() {
  const s = useTick(3, 1300);
  const tiers = [["Automatic", "bg-emerald-500", "Restart Outlook"], ["Approval", "bg-amber-500", "Network reset"], ["Admin only", "bg-red-500", "Disable account"]];
  return (
    <div className="flex h-full flex-col justify-center gap-2 px-3">
      <div className="grid grid-cols-3 gap-1.5">
        {tiers.map(([t, c], i) => (
          <span key={t} className={`rounded-md py-1 text-center text-[9px] font-semibold ${s === i ? `${c} text-white` : "bg-surface text-muted-token"}`}>{t}</span>
        ))}
      </div>
      <p className="text-center text-[10px]"><span className="font-semibold">{tiers[s][2]}</span> → {tiers[s][0].toLowerCase()} tier</p>
    </div>
  );
}

/* 9 — Reporting: bars growing */
function Reports() {
  return (
    <div className="flex h-full items-end justify-center gap-2 p-3">
      {[40, 65, 50, 80, 70, 92].map((h, i) => (
        <motion.div key={i} className="w-4 rounded-t bg-gradient-to-t from-brand-600 to-cyan-400" animate={{ height: ["10%", `${h}%`, `${h}%`] }} transition={loop(3, i * 0.12)} />
      ))}
      <FileText className="mb-1 ml-2 h-6 w-6 text-brand-500" />
    </div>
  );
}

/* 10 — Notifications: a bell and an alert that needs a decision */
function Notify() {
  return (
    <div className="flex h-full items-center justify-center gap-3">
      <motion.span animate={{ rotate: [0, -15, 15, -10, 0] }} transition={{ duration: 0.8, repeat: Infinity, repeatDelay: 1.4 }} className="relative">
        <Bell className="h-7 w-7 text-brand-500" />
        <span className="absolute -right-1 -top-1 grid h-3.5 w-3.5 place-items-center rounded-full bg-red-500 text-[8px] text-white">1</span>
      </motion.span>
      <Row className="shadow-sm"><span className="font-semibold">Approval needed:</span> network reset on OPS-LT-21</Row>
    </div>
  );
}

/* 11 — Audit trail: entries scrolling in */
function Audit() {
  const lines = ["10:41 restart_outlook · DESIGN-WS-07 · auto", "10:43 network_reset · approved by admin", "10:44 policy updated · priya@acme", "10:46 clear_temp · FIN-LT-03 · auto", "10:47 user disabled · rahul.k"];
  const s = useTick(lines.length, 1000);
  const view = [0, 1, 2].map((k) => lines[(s + k) % lines.length]);
  return (
    <div className="space-y-1 p-2.5 font-mono">
      {view.map((l) => (
        <motion.div key={l} layout initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="truncate rounded bg-surface px-2 py-1 text-[9px] text-secondary-token">{l}</motion.div>
      ))}
    </div>
  );
}

/* 12 — Compliance: a posture score filling up */
function Compliance() {
  return (
    <div className="flex h-full items-center justify-center gap-4">
      <svg viewBox="0 0 40 40" className="h-16 w-16 -rotate-90">
        <circle cx="20" cy="20" r="16" fill="none" stroke="var(--border)" strokeWidth="4" />
        <motion.circle cx="20" cy="20" r="16" fill="none" stroke="#10b981" strokeWidth="4" strokeLinecap="round" initial={{ pathLength: 0 }} animate={{ pathLength: [0, 0.86, 0.86] }} transition={loop(3)} />
      </svg>
      <div className="text-[10px]"><p className="font-semibold">Posture score</p><p className="text-emerald-500">BitLocker · Defender · updates</p><p className="text-amber-500">2 devices need attention</p></div>
    </div>
  );
}

/* 13 — Restricted software: one app flagged in a list */
function Restricted() {
  const s = useTick(2, 1400);
  return (
    <div className="space-y-1 p-2.5">
      {["Microsoft Teams", "uTorrent", "Google Chrome"].map((a, i) => (
        <Row key={a} className={i === 1 && s === 1 ? "ring-1 ring-red-500" : ""}>
          {a}
          {i === 1 && s === 1 && <motion.span initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="ml-auto font-semibold text-red-500">restricted</motion.span>}
        </Row>
      ))}
    </div>
  );
}

/* 14 — Fleet correlation: the same fault on many devices, healed together */
function Correlation() {
  const s = useTick(3, 1200);
  const bad = [2, 5, 9, 12, 16];
  return (
    <div className="flex h-full items-center justify-center gap-3">
      <div className="grid grid-cols-6 gap-1.5">
        {Array.from({ length: 18 }, (_, i) => {
          const hit = bad.includes(i);
          const c = !hit ? "bg-emerald-500/60" : s === 0 ? "bg-red-500" : s === 1 ? "bg-amber-500" : "bg-emerald-500";
          return <motion.span key={i} className={`h-3 w-3 rounded-sm ${c}`} animate={hit && s === 1 ? { scale: [1, 1.3, 1] } : { scale: 1 }} transition={{ duration: 0.6, repeat: hit && s === 1 ? Infinity : 0 }} />;
        })}
      </div>
      <span className="w-20 text-[10px] font-semibold">{["Same DNS fault on 5", "Fixing all 5…", "All 5 healthy"][s]}</span>
    </div>
  );
}

/* 15 — Helpdesk integration: a ticket handed over with evidence */
function Helpdesk() {
  return (
    <div className="relative flex h-full items-center justify-between px-4">
      <span className="text-[10px] font-semibold">SAVIO</span>
      <motion.div className="absolute left-12" animate={{ x: [0, 120, 120], opacity: [1, 1, 0] }} transition={loop(2.4)}>
        <Row className="shadow"><Ticket className="h-3 w-3 text-brand-500" /> + evidence</Row>
      </motion.div>
      <span className="rounded-md bg-surface px-2 py-1 text-[10px] font-semibold">Freshservice</span>
    </div>
  );
}

/* 16 — Self-learning KB: a confirmed fix becomes knowledge */
function Learning() {
  const s = useTick(3, 1200);
  return (
    <div className="flex h-full items-center justify-center gap-3">
      <BookOpen className="h-8 w-8 text-brand-500" />
      <div className="text-[10px]">
        <p className="font-semibold">“Outlook stuck on loading profile”</p>
        <p className="text-muted-token">{["Fix confirmed by user", "Added to knowledge base", "Suggested first next time"][s]}</p>
        <div className="mt-1 h-1 w-28 overflow-hidden rounded-full bg-surface"><motion.div className="h-full bg-emerald-500" animate={{ width: `${30 + s * 30}%` }} /></div>
      </div>
    </div>
  );
}

/* 17 — Asset assignment: an email asking for acknowledgement */
function Assignment() {
  const s = useTick(3, 1200);
  return (
    <div className="flex h-full items-center justify-center gap-3">
      <Laptop className="h-7 w-7 text-brand-500" />
      <motion.span animate={{ x: [0, 6, 0] }} transition={loop(1.2)}><Mail className="h-5 w-5 text-cyan-500" /></motion.span>
      <div className="text-[10px]">
        <p className="font-semibold">ThinkPad T14 → Meera</p>
        <p className={s === 2 ? "text-emerald-500" : "text-muted-token"}>{["Email sent from it@acme.com", "Waiting for receipt…", "Acknowledged ✓ on asset record"][s]}</p>
      </div>
    </div>
  );
}

/* 18 — Remote support with consent: the user allows, then it connects */
function Remote() {
  const s = useTick(3, 1300);
  return (
    <div className="flex h-full items-center justify-center gap-3">
      <MonitorSmartphone className="h-8 w-8 text-brand-500" />
      <div className="rounded-lg bg-surface p-2 text-[10px] shadow-sm">
        <p className="font-semibold">IT (Priya) wants to view your screen</p>
        {s === 0 && <div className="mt-1 flex gap-1"><span className="rounded bg-brand-600 px-2 py-0.5 text-white">Allow</span><span className="rounded border border-token px-2 py-0.5">Deny</span></div>}
        {s === 1 && <p className="mt-1 text-brand-500">Allowed — connecting…</p>}
        {s === 2 && <p className="mt-1 text-emerald-500">Connected · live, not recorded</p>}
      </div>
    </div>
  );
}

// Matched on the card's TITLE, not its position: the live list comes from content.json, whose
// order is edited independently of the defaults in code — matching by index put the
// notifications bell on the audit-trail card. Order matters only where titles overlap
// ("Asset Assignment" before "Asset Inventory"); a card with no match shows no scene.
const SCENES: [RegExp, () => ReactNode][] = [
  [/assignment|acknowledg/i, Assignment],
  [/inventory/i, Inventory],
  [/telemetry/i, Telemetry],
  [/cognitive|reasoning/i, Cognitive],
  [/self-heal|self heal/i, SelfHeal],
  [/patch|update/i, Patch],
  [/offboard/i, Offboard],
  [/conversation|chat/i, Chat],
  [/approval|tier/i, Tiers],
  [/report/i, Reports],
  [/notif|alert/i, Notify],
  [/audit/i, Audit],
  [/complian|posture/i, Compliance],
  [/restricted|software/i, Restricted],
  [/correlat|mass/i, Correlation],
  [/helpdesk|ticket/i, Helpdesk],
  [/learning|knowledge/i, Learning],
  [/remote|consent/i, Remote],
];

/**
 * The agentic loop, run: a signal walks the six steps in order, the active one lights up and
 * shows what it found on one example ticket, and the connector fills as evidence accumulates.
 */
const LOOP_EXAMPLE = [
  "“Outlook won't open”",
  "Hung-profile fix found",
  "Event 1000 × 3 today",
  "High — safe to act",
  "Restart Outlook · auto",
  "Opens ✓ · KB updated",
];

export function WorkflowLoop({ steps }: { steps: { label: string; desc: string; Icon: typeof Bell }[] }) {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { margin: "-15% 0px" });
  const [active, setActive] = useState(0);
  useEffect(() => {
    if (!inView) return;
    const id = window.setInterval(() => setActive((a) => (a + 1) % (steps.length + 1)), 1300);
    return () => window.clearInterval(id);
  }, [inView, steps.length]);

  return (
    <div ref={ref} className="relative mt-14">
      {/* the connector the signal travels along (desktop row only) */}
      <div className="absolute left-[8%] right-[8%] top-[38px] hidden h-0.5 rounded-full lg:block" style={{ background: "var(--border)" }}>
        <motion.div
          className="h-full rounded-full bg-gradient-to-r from-brand-600 to-cyan-400"
          animate={{ width: `${(Math.min(active, steps.length - 1) / (steps.length - 1)) * 100}%` }}
          transition={{ duration: 0.6 }}
        />
      </div>
      <div className="grid gap-4 sm:grid-cols-3 lg:grid-cols-6">
        {steps.map(({ label, desc, Icon }, i) => {
          const on = i === active;
          const done = i < active;
          return (
            <motion.div
              key={label}
              animate={{ y: on ? -6 : 0, scale: on ? 1.04 : 1 }}
              transition={{ type: "spring", stiffness: 300, damping: 22 }}
              className={`relative h-full rounded-2xl border bg-surface p-5 text-center transition-colors ${on ? "border-brand-500 shadow-[0_12px_40px_-12px_rgba(37,99,235,0.55)]" : "border-token"}`}
            >
              <div className={`relative mx-auto grid h-11 w-11 place-items-center rounded-xl transition-colors ${on || done ? "bg-brand-600 text-white" : "bg-brand-500/10 text-brand-500"}`}>
                {on && <span className="absolute inset-0 animate-ping rounded-xl bg-brand-500/40" />}
                {done ? <CheckCircle2 className="relative h-5 w-5" /> : <Icon className="relative h-5 w-5" />}
              </div>
              <div className="mt-3 text-sm font-bold">{label}</div>
              <div className="mt-1 text-xs text-muted-token">{desc}</div>
              <div className={`mt-2 min-h-[28px] rounded-md px-1.5 py-1 text-[10px] font-medium transition-all ${on || done ? "bg-cyan-500/10 text-cyan-700 opacity-100 dark:text-cyan-300" : "opacity-0"}`}>
                {LOOP_EXAMPLE[i] ?? ""}
              </div>
              <span className="absolute -top-2 left-3 text-xs font-bold text-brand-500/50">{String(i + 1).padStart(2, "0")}</span>
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}

export function CapabilityVisual({ title }: { title: string }) {
  const Scene = SCENES.find(([re]) => re.test(title))?.[1];
  if (!Scene) return null;
  return <Frame><Scene /></Frame>;
}
