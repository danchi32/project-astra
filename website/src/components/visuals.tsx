"use client";

import { motion } from "framer-motion";
import {
  Activity,
  Cpu,
  HardDrive,
  MemoryStick,
  ShieldCheck,
  Sparkles,
  Search,
  Stethoscope,
  Wrench,
  BadgeCheck,
  Laptop,
  CheckCircle2,
  DownloadCloud,
  Send,
  Loader2,
} from "lucide-react";
import { useEffect, useState } from "react";

/* ----------------------------------------------------------------------------
 * Small window chrome shared by every mock panel.
 * ------------------------------------------------------------------------- */
function Chrome({
  title,
  children,
  className = "",
}: {
  title: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`overflow-hidden rounded-2xl border border-token bg-surface shadow-2xl ${className}`}
    >
      <div className="flex items-center gap-2 border-b border-token bg-surface-2 px-4 py-3">
        <span className="h-3 w-3 rounded-full bg-red-400/80" />
        <span className="h-3 w-3 rounded-full bg-amber-400/80" />
        <span className="h-3 w-3 rounded-full bg-emerald-400/80" />
        <span className="ml-3 text-xs font-medium text-muted-token">
          {title}
        </span>
      </div>
      <div className="p-4">{children}</div>
    </div>
  );
}

/* ----------------------------------------------------------------------------
 * Animated bar that eases to a value and gently breathes.
 * ------------------------------------------------------------------------- */
function LiveBar({
  value,
  color,
}: {
  value: number;
  color: string;
}) {
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-surface-2">
      <motion.div
        className={`h-full rounded-full ${color}`}
        initial={{ width: 0 }}
        whileInView={{ width: `${value}%` }}
        viewport={{ once: true }}
        transition={{ duration: 1.1, ease: "easeOut" }}
      />
    </div>
  );
}

/* ============================================================================
 * HERO DASHBOARD — fleet overview with live telemetry + an AI action ticker.
 * ========================================================================= */
export function DashboardMockup() {
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setTick((t) => (t + 1) % actions.length), 2400);
    return () => clearInterval(id);
  }, []);

  const actions = [
    { icon: Wrench, text: "Restarted Explorer on FIN-LT-14", tone: "emerald" },
    { icon: Activity, text: "Flushed DNS on SALES-PC-03", tone: "blue" },
    { icon: ShieldCheck, text: "Approval requested: Office repair", tone: "amber" },
    { icon: BadgeCheck, text: "Verified fix on DESIGN-WS-07", tone: "emerald" },
  ];

  const tones: Record<string, string> = {
    emerald: "text-emerald-500 bg-emerald-500/10",
    blue: "text-brand-500 bg-brand-500/10",
    amber: "text-amber-500 bg-amber-500/10",
  };
  const Cur = actions[tick].icon;

  return (
    <Chrome title="astra.technomateai.com — Fleet Dashboard">
      <div className="grid grid-cols-3 gap-3">
        {[
          { label: "Devices online", value: "248", sub: "/ 256", accent: "text-emerald-500" },
          { label: "Issues auto-healed", value: "1,204", sub: "this month", accent: "text-brand-500" },
          { label: "Avg. resolve time", value: "38s", sub: "−72% vs manual", accent: "text-violet-500" },
        ].map((s) => (
          <div key={s.label} className="rounded-xl border border-token bg-surface-2 p-3">
            <div className="text-xs text-muted-token">{s.label}</div>
            <div className="mt-1 flex items-baseline gap-1">
              <span className={`text-xl font-bold ${s.accent}`}>{s.value}</span>
              <span className="text-[11px] text-muted-token">{s.sub}</span>
            </div>
          </div>
        ))}
      </div>

      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <div className="rounded-xl border border-token bg-surface-2 p-3.5">
          <div className="mb-3 flex items-center gap-2 text-xs font-semibold">
            <Cpu className="h-4 w-4 text-brand-500" /> Live telemetry
          </div>
          {[
            { l: "CPU", v: 42, c: "bg-brand-500" },
            { l: "Memory", v: 61, c: "bg-violet-500" },
            { l: "Disk", v: 74, c: "bg-amber-500" },
          ].map((r) => (
            <div key={r.l} className="mb-2.5 last:mb-0">
              <div className="mb-1 flex justify-between text-[11px] text-muted-token">
                <span>{r.l}</span>
                <span>{r.v}%</span>
              </div>
              <LiveBar value={r.v} color={r.c} />
            </div>
          ))}
        </div>

        <div className="rounded-xl border border-token bg-surface-2 p-3.5">
          <div className="mb-3 flex items-center gap-2 text-xs font-semibold">
            <Sparkles className="h-4 w-4 text-brand-500" /> ASTRA activity
          </div>
          <div className="relative h-[104px] overflow-hidden">
            <motion.div
              key={tick}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4 }}
              className="flex items-center gap-2.5"
            >
              <span
                className={`grid h-8 w-8 place-items-center rounded-lg ${tones[actions[tick].tone]}`}
              >
                <Cur className="h-4 w-4" />
              </span>
              <span className="text-xs font-medium text-primary-token">
                {actions[tick].text}
              </span>
            </motion.div>
            <div className="mt-3 space-y-2 opacity-60">
              {actions
                .filter((_, i) => i !== tick)
                .slice(0, 3)
                .map((a, i) => (
                  <div key={i} className="flex items-center gap-2.5 text-[11px] text-muted-token">
                    <a.icon className="h-3.5 w-3.5" />
                    <span>{a.text}</span>
                  </div>
                ))}
            </div>
          </div>
        </div>
      </div>
    </Chrome>
  );
}

/* ============================================================================
 * SELF-HEALING FLOW — animated Evidence → Decision → Heal → Verify pipeline.
 * ========================================================================= */
export function SelfHealingFlow() {
  const steps = [
    { icon: Search, label: "Detect", desc: "Telemetry anomaly" },
    { icon: Stethoscope, label: "Diagnose", desc: "Root-cause + confidence" },
    { icon: ShieldCheck, label: "Decide", desc: "Approval tier check" },
    { icon: Wrench, label: "Heal", desc: "Allowlisted action" },
    { icon: BadgeCheck, label: "Verify", desc: "Confirm resolved" },
  ];
  return (
    <div className="rounded-2xl border border-token bg-surface p-5 sm:p-7">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-stretch sm:gap-2">
        {steps.map((s, i) => (
          <div key={s.label} className="flex flex-1 items-center gap-3 sm:flex-col sm:gap-3 sm:text-center">
            <motion.div
              initial={{ scale: 0.6, opacity: 0 }}
              whileInView={{ scale: 1, opacity: 1 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.15, type: "spring", stiffness: 220 }}
              className="relative grid h-12 w-12 shrink-0 place-items-center rounded-xl border border-brand-500/30 bg-brand-500/10 text-brand-500"
            >
              <s.icon className="h-5 w-5" />
              <motion.span
                className="absolute inset-0 rounded-xl border border-brand-500/50"
                animate={{ opacity: [0.6, 0, 0.6], scale: [1, 1.35, 1] }}
                transition={{ duration: 2.4, repeat: Infinity, delay: i * 0.3 }}
              />
            </motion.div>
            <div className="sm:mt-1">
              <div className="text-sm font-semibold">{s.label}</div>
              <div className="text-xs text-muted-token">{s.desc}</div>
            </div>
            {i < steps.length - 1 && (
              <div className="hidden flex-1 sm:block" aria-hidden>
                <div className="mt-6 h-px w-full bg-gradient-to-r from-brand-500/40 to-transparent" />
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

/* ============================================================================
 * INVENTORY PANEL — asset rows that stream in.
 * ========================================================================= */
export function InventoryPanel() {
  const rows = [
    { name: "FIN-LT-14", type: "Laptop • Dell 5540", status: "Healthy", cpu: "i7 · 16GB", tone: "emerald" },
    { name: "SALES-PC-03", type: "Desktop • HP 400", status: "Healthy", cpu: "i5 · 8GB", tone: "emerald" },
    { name: "DESIGN-WS-07", type: "Workstation • Z4", status: "Updating", cpu: "Xeon · 64GB", tone: "amber" },
    { name: "HR-LT-22", type: "Laptop • Lenovo T14", status: "Healthy", cpu: "i5 · 16GB", tone: "emerald" },
    { name: "OPS-PC-11", type: "Desktop • Dell 3080", status: "Attention", cpu: "i3 · 8GB", tone: "red" },
  ];
  const tones: Record<string, string> = {
    emerald: "text-emerald-500 bg-emerald-500/10",
    amber: "text-amber-500 bg-amber-500/10",
    red: "text-red-500 bg-red-500/10",
  };
  return (
    <Chrome title="Assets & Inventory">
      <div className="mb-3 grid grid-cols-12 gap-2 px-1 text-[11px] font-medium uppercase tracking-wide text-muted-token">
        <div className="col-span-5">Device</div>
        <div className="col-span-4">Specs</div>
        <div className="col-span-3 text-right">Status</div>
      </div>
      <div className="space-y-2">
        {rows.map((r, i) => (
          <motion.div
            key={r.name}
            initial={{ opacity: 0, x: -14 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            transition={{ delay: i * 0.12 }}
            className="grid grid-cols-12 items-center gap-2 rounded-lg border border-token bg-surface-2 px-3 py-2.5"
          >
            <div className="col-span-5 flex items-center gap-2">
              <Laptop className="h-4 w-4 text-brand-500" />
              <div>
                <div className="text-xs font-semibold">{r.name}</div>
                <div className="text-[10px] text-muted-token">{r.type}</div>
              </div>
            </div>
            <div className="col-span-4 text-[11px] text-secondary-token">{r.cpu}</div>
            <div className="col-span-3 flex justify-end">
              <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${tones[r.tone]}`}>
                {r.status}
              </span>
            </div>
          </motion.div>
        ))}
      </div>
    </Chrome>
  );
}

/* ============================================================================
 * TELEMETRY GAUGES — radial-ish live metrics.
 * ========================================================================= */
export function TelemetryGauges() {
  const metrics = [
    { icon: Cpu, label: "CPU", value: 42, color: "#b246d4" },
    { icon: MemoryStick, label: "Memory", value: 61, color: "#8b5cf6" },
    { icon: HardDrive, label: "Disk", value: 74, color: "#f59e0b" },
  ];
  return (
    <Chrome title="Telemetry — DESIGN-WS-07">
      <div className="grid grid-cols-3 gap-3">
        {metrics.map((m) => {
          const r = 26;
          const c = 2 * Math.PI * r;
          return (
            <div key={m.label} className="flex flex-col items-center rounded-xl border border-token bg-surface-2 p-3">
              <div className="relative h-[72px] w-[72px]">
                <svg viewBox="0 0 64 64" className="h-full w-full -rotate-90">
                  <circle cx="32" cy="32" r={r} fill="none" stroke="var(--border)" strokeWidth="7" />
                  <motion.circle
                    cx="32"
                    cy="32"
                    r={r}
                    fill="none"
                    stroke={m.color}
                    strokeWidth="7"
                    strokeLinecap="round"
                    strokeDasharray={c}
                    initial={{ strokeDashoffset: c }}
                    whileInView={{ strokeDashoffset: c - (c * m.value) / 100 }}
                    viewport={{ once: true }}
                    transition={{ duration: 1.2, ease: "easeOut" }}
                  />
                </svg>
                <div className="absolute inset-0 grid place-items-center">
                  <span className="text-sm font-bold">{m.value}%</span>
                </div>
              </div>
              <div className="mt-2 flex items-center gap-1.5 text-xs text-secondary-token">
                <m.icon className="h-3.5 w-3.5" /> {m.label}
              </div>
            </div>
          );
        })}
      </div>
    </Chrome>
  );
}

/* ============================================================================
 * AI CONSOLE — an animated agentic tool-use conversation.
 * ========================================================================= */
export function AiConsole() {
  const lines = [
    { who: "user", text: "My Teams keeps crashing and audio cuts out." },
    { who: "tool", text: "🔍 Searching knowledge base… 3 matches" },
    { who: "tool", text: "📡 Collecting telemetry — Teams, audio driver, network" },
    { who: "astra", text: "Confidence 94%: corrupt Teams cache + stale audio driver." },
    { who: "tool", text: "🛠 Clearing Teams cache (automatic tier)…" },
    { who: "astra", text: "Fixed & verified. Driver update needs your approval →" },
  ];
  const [n, setN] = useState(1);
  useEffect(() => {
    const id = setInterval(
      () => setN((v) => (v >= lines.length ? 1 : v + 1)),
      1300,
    );
    return () => clearInterval(id);
  }, [lines.length]);

  const styles: Record<string, string> = {
    user: "bg-surface-2 text-primary-token self-end",
    tool: "bg-brand-500/10 text-brand-600 dark:text-brand-300 font-mono text-[11px]",
    astra: "bg-violet-500/10 text-violet-600 dark:text-violet-300",
  };

  return (
    <Chrome title="ASTRA Assistant">
      <div className="mini-scroll flex h-[220px] flex-col gap-2 overflow-hidden">
        {lines.slice(0, n).map((l, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className={`max-w-[85%] rounded-xl px-3 py-2 text-xs leading-relaxed ${styles[l.who]} ${
              l.who === "user" ? "ml-auto" : ""
            }`}
          >
            {l.who === "astra" && (
              <span className="mb-0.5 flex items-center gap-1 text-[10px] font-bold uppercase tracking-wide text-violet-500">
                <Sparkles className="h-3 w-3" /> ASTRA
              </span>
            )}
            {l.text}
          </motion.div>
        ))}
        {n < lines.length && (
          <div className="flex items-center gap-1 px-1">
            {[0, 1, 2].map((d) => (
              <motion.span
                key={d}
                className="h-1.5 w-1.5 rounded-full bg-brand-500"
                animate={{ opacity: [0.3, 1, 0.3] }}
                transition={{ duration: 1, repeat: Infinity, delay: d * 0.2 }}
              />
            ))}
          </div>
        )}
      </div>
    </Chrome>
  );
}

/* ============================================================================
 * APPROVAL TIERS — the three-tier remediation model.
 * ========================================================================= */
export function ApprovalTiers() {
  const tiers = [
    {
      name: "Automatic",
      color: "emerald",
      icon: CheckCircle2,
      desc: "Safe, reversible fixes run instantly.",
      items: ["Restart Explorer / services", "Flush DNS", "Clear temp files", "Restart adapter"],
    },
    {
      name: "Approval required",
      color: "amber",
      icon: ShieldCheck,
      desc: "A human approves before ASTRA acts.",
      items: ["Office repair", "Driver update", "Network reset"],
    },
    {
      name: "Admin only",
      color: "red",
      icon: Wrench,
      desc: "High-impact changes, admins only.",
      items: ["Registry edits", "BIOS / firmware", "Windows reinstall"],
    },
  ];
  const ring: Record<string, string> = {
    emerald: "border-emerald-500/30 bg-emerald-500/[0.06]",
    amber: "border-amber-500/30 bg-amber-500/[0.06]",
    red: "border-red-500/30 bg-red-500/[0.06]",
  };
  const chip: Record<string, string> = {
    emerald: "text-emerald-500 bg-emerald-500/10",
    amber: "text-amber-500 bg-amber-500/10",
    red: "text-red-500 bg-red-500/10",
  };
  return (
    <div className="grid gap-4 md:grid-cols-3">
      {tiers.map((t, i) => (
        <motion.div
          key={t.name}
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ delay: i * 0.12 }}
          className={`rounded-2xl border p-5 ${ring[t.color]}`}
        >
          <div className={`inline-grid h-10 w-10 place-items-center rounded-xl ${chip[t.color]}`}>
            <t.icon className="h-5 w-5" />
          </div>
          <h3 className="mt-3 text-base font-bold">{t.name}</h3>
          <p className="mt-1 text-sm text-secondary-token">{t.desc}</p>
          <ul className="mt-3 space-y-1.5">
            {t.items.map((it) => (
              <li key={it} className="flex items-center gap-2 text-xs text-secondary-token">
                <span className={`h-1.5 w-1.5 rounded-full ${chip[t.color]}`} />
                {it}
              </li>
            ))}
          </ul>
        </motion.div>
      ))}
    </div>
  );
}

/* ============================================================================
 * PATCH PUSH — admin pushes a Windows Update to the fleet; devices roll
 * through Pending → Downloading → Installing → Installed with a rollout ring.
 * ========================================================================= */
export function PatchPushPanel() {
  const devices = ["FIN-LT-14", "SALES-PC-03", "DESIGN-WS-07", "HR-LT-22", "OPS-PC-11"];
  const [p, setP] = useState(0);

  useEffect(() => {
    const id = setInterval(() => setP((v) => (v >= 155 ? 0 : v + 1)), 55);
    return () => clearInterval(id);
  }, []);

  // Staggered per-device progress, 0–100.
  const local = (i: number) =>
    Math.max(0, Math.min(100, ((p - i * 16) / 45) * 100));
  const statusOf = (v: number) =>
    v <= 0 ? "pending" : v >= 100 ? "installed" : v < 55 ? "downloading" : "installing";

  const installed = devices.filter((_, i) => local(i) >= 100).length;
  const overall = Math.round(
    devices.reduce((a, _, i) => a + local(i), 0) / devices.length,
  );

  const meta: Record<
    string,
    { label: string; text: string; bar: string; icon?: React.ReactNode }
  > = {
    pending: { label: "Pending", text: "text-muted-token", bar: "bg-transparent" },
    downloading: {
      label: "Downloading",
      text: "text-brand-500",
      bar: "bg-brand-500",
      icon: <DownloadCloud className="h-3.5 w-3.5" />,
    },
    installing: {
      label: "Installing",
      text: "text-violet-500",
      bar: "bg-violet-500",
      icon: <Loader2 className="h-3.5 w-3.5 animate-spin" />,
    },
    installed: {
      label: "Installed",
      text: "text-emerald-500",
      bar: "bg-emerald-500",
      icon: <CheckCircle2 className="h-3.5 w-3.5" />,
    },
  };

  const R = 26;
  const C = 2 * Math.PI * R;

  return (
    <Chrome title="Admin · Windows Updates">
      {/* Header: the update + push action */}
      <div className="flex items-center justify-between gap-3 rounded-xl border border-token bg-surface-2 p-3.5">
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-xs font-semibold">
            <ShieldCheck className="h-4 w-4 shrink-0 text-brand-500" />
            <span className="truncate">KB5039211 · Cumulative Update</span>
          </div>
          <div className="mt-0.5 text-[11px] text-muted-token">
            Security · 2025-07 · pushed to {devices.length} devices
          </div>
        </div>
        <motion.div
          className="inline-flex shrink-0 items-center gap-1.5 rounded-lg bg-brand-600 px-3 py-2 text-[11px] font-semibold text-white"
          animate={{ boxShadow: ["0 0 0 0 rgba(37,99,235,0.5)", "0 0 0 8px rgba(37,99,235,0)"] }}
          transition={{ duration: 1.8, repeat: Infinity }}
        >
          <Send className="h-3.5 w-3.5" /> Push to fleet
        </motion.div>
      </div>

      <div className="mt-3 grid gap-3 sm:grid-cols-[auto,1fr]">
        {/* Rollout ring */}
        <div className="flex flex-col items-center justify-center rounded-xl border border-token bg-surface-2 p-3">
          <div className="relative h-[84px] w-[84px]">
            <svg viewBox="0 0 64 64" className="h-full w-full -rotate-90">
              <circle cx="32" cy="32" r={R} fill="none" stroke="var(--border)" strokeWidth="7" />
              <circle
                cx="32"
                cy="32"
                r={R}
                fill="none"
                stroke="#9a2fbb"
                strokeWidth="7"
                strokeLinecap="round"
                strokeDasharray={C}
                strokeDashoffset={C - (C * overall) / 100}
                style={{ transition: "stroke-dashoffset 0.2s linear" }}
              />
            </svg>
            <div className="absolute inset-0 grid place-items-center">
              <span className="text-lg font-bold">{overall}%</span>
            </div>
          </div>
          <div className="mt-1.5 text-[11px] text-muted-token">
            {installed}/{devices.length} installed
          </div>
        </div>

        {/* Per-device rollout */}
        <div className="space-y-2">
          {devices.map((name, i) => {
            const v = local(i);
            const s = statusOf(v);
            const m = meta[s];
            return (
              <div
                key={name}
                className="rounded-lg border border-token bg-surface-2 px-3 py-2"
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <Laptop className="h-3.5 w-3.5 text-brand-500" />
                    <span className="text-xs font-semibold">{name}</span>
                  </div>
                  <span className={`flex items-center gap-1 text-[11px] font-medium ${m.text}`}>
                    {m.icon}
                    {m.label}
                  </span>
                </div>
                <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-app">
                  <div
                    className={`h-full rounded-full ${m.bar}`}
                    style={{ width: `${v}%`, transition: "width 0.2s linear" }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </Chrome>
  );
}
