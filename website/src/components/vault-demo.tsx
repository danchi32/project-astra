"use client";

import { AnimatePresence, motion } from "framer-motion";
import { CheckCircle2, Lock, MousePointer2, Pause, Play, ShieldCheck } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

/**
 * The product demonstrating itself, in place of a screen recording.
 *
 * A recording would have to be re-shot for every interface change, ships as a file that
 * ignores the visitor's theme, and cannot be read by anything but eyes. This plays the same
 * five beats as markup: it follows the site's tokens into dark mode, stays crisp at any
 * width, and leaves real text on the page. It advances on a timer and loops, so a visitor
 * who scrolls past sees the whole thing without pressing anything.
 */

const SCENES = [
  { key: "open", label: "Open" },
  { key: "cover", label: "Sign-in" },
  { key: "fill", label: "Filled" },
  { key: "in", label: "Signed in" },
  { key: "record", label: "Recorded" },
] as const;

const HOLD_MS = 2800;

export function VaultDemo() {
  const [scene, setScene] = useState(0);
  const [playing, setPlaying] = useState(true);

  // Someone who has asked their system for less motion gets the first frame and the controls,
  // not a panel that changes under them.
  useEffect(() => {
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    if (query.matches) setPlaying(false);
  }, []);

  useEffect(() => {
    if (!playing) return;
    const timer = setTimeout(() => setScene((value) => (value + 1) % SCENES.length), HOLD_MS);
    return () => clearTimeout(timer);
  }, [playing, scene]);

  const go = useCallback((index: number) => { setPlaying(false); setScene(index); }, []);

  return (
    <div className="overflow-hidden rounded-2xl border border-token bg-surface shadow-2xl">
      <div className="flex items-center gap-2 border-b border-token bg-surface-2 px-4 py-3">
        <span className="h-3 w-3 rounded-full bg-red-400/80" />
        <span className="h-3 w-3 rounded-full bg-amber-400/80" />
        <span className="h-3 w-3 rounded-full bg-emerald-400/80" />
        <span className="ml-3 truncate text-xs font-medium text-muted-token">
          Secure Vault — {SCENES[scene].label}
        </span>
        <button
          type="button"
          onClick={() => setPlaying((value) => !value)}
          aria-label={playing ? "Pause the demo" : "Play the demo"}
          className="ml-auto grid h-6 w-6 flex-none place-items-center rounded-full border border-token bg-surface text-muted-token transition-colors hover:text-brand-500"
        >
          {playing ? <Pause className="h-3 w-3" /> : <Play className="h-3 w-3" />}
        </button>
      </div>

      <div className="relative min-h-[262px] p-4">
        <AnimatePresence mode="wait">
          <motion.div
            key={SCENES[scene].key}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.35 }}
          >
            {scene === 0 && <SceneOpen />}
            {scene === 1 && <SceneCover />}
            {scene === 2 && <SceneFill />}
            {scene === 3 && <SceneIn />}
            {scene === 4 && <SceneRecord />}
          </motion.div>
        </AnimatePresence>
      </div>

      {/* A scrubber, so the panel reads as something playing rather than something twitching. */}
      <div className="flex items-center gap-1.5 border-t border-token bg-surface-2 px-4 py-2.5">
        {SCENES.map((item, index) => (
          <button
            key={item.key}
            type="button"
            onClick={() => go(index)}
            className="group flex-1"
            aria-label={`Show step ${index + 1}: ${item.label}`}
          >
            <span className="block h-1 overflow-hidden rounded-full bg-surface">
              <motion.span
                className="block h-full rounded-full bg-brand-500"
                initial={false}
                animate={{ width: index < scene ? "100%" : index === scene ? "100%" : "0%" }}
                transition={{ duration: index === scene && playing ? HOLD_MS / 1000 : 0.25, ease: "linear" }}
              />
            </span>
            <span className={`mt-1.5 block text-[9px] font-semibold ${index === scene ? "text-brand-500" : "text-muted-token"}`}>
              {item.label}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}

/* -- 1. The person picks a portal. There is nothing to type and nothing to look up. -------- */
function SceneOpen() {
  const portals = [
    { name: "Northwind Portal", letter: "N" },
    { name: "Lakeside VMS", letter: "L" },
    { name: "Redwood Staffing", letter: "R" },
  ];
  return (
    <div className="relative space-y-2">
      {portals.map((portal, index) => (
        <div
          key={portal.name}
          className={`flex items-center gap-2.5 rounded-lg border px-3 py-2.5 transition-colors ${index === 0 ? "border-brand-500/50 bg-brand-500/5" : "border-token bg-surface-2"}`}
        >
          <span className="grid h-8 w-8 flex-none place-items-center rounded-lg bg-brand-500/10 text-xs font-bold text-brand-500">{portal.letter}</span>
          <div className="min-w-0 flex-1">
            <div className="truncate text-xs font-semibold">{portal.name}</div>
            <div className="flex items-center gap-1 text-[10px] text-muted-token">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" /> Credentials protected
            </div>
          </div>
          <span className="flex-none rounded-md bg-brand-600 px-2.5 py-1 text-[10px] font-bold text-white">Open</span>
        </div>
      ))}
      <motion.div
        className="pointer-events-none absolute right-8 top-3 text-brand-500"
        initial={{ x: 28, y: 46, opacity: 0 }}
        animate={{ x: 0, y: 0, opacity: 1 }}
        transition={{ duration: 1, ease: "easeOut" }}
      >
        <MousePointer2 className="h-4 w-4 fill-brand-500" />
      </motion.div>
    </div>
  );
}

/* -- 2. The screen the person actually sees while their credential is used. ---------------- */
function SceneCover() {
  return (
    <div className="grid min-h-[230px] place-items-center rounded-lg border border-token bg-surface-2">
      <div className="text-center">
        <motion.span
          className="mx-auto block h-8 w-8 rounded-full border-2 border-brand-500/25 border-t-brand-500"
          animate={{ rotate: 360 }}
          transition={{ repeat: Infinity, duration: 0.9, ease: "linear" }}
        />
        <p className="mt-4 text-[11px] font-bold tracking-[0.12em] text-brand-500">SECURE SIGN-IN IN PROGRESS…</p>
        <p className="mt-2 text-[10px] text-muted-token">The portal&apos;s form is covered while it is filled.</p>
      </div>
    </div>
  );
}

/* -- 3. The point of the product: filled, submitted, and never readable. ------------------- */
function SceneFill() {
  const fields = [
    { label: "Username", value: "recruiter@company.com", delay: 0.1 },
    { label: "Password", value: "Th3-P0rtal-Secret", delay: 0.5 },
  ];
  return (
    <div className="space-y-3 rounded-lg border border-token bg-surface-2 p-4">
      {fields.map((field) => (
        <motion.div key={field.label} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: field.delay }}>
          <div className="text-[10px] font-semibold uppercase tracking-wide text-muted-token">{field.label}</div>
          <div className="mt-1 flex items-center gap-2 rounded-md border border-token bg-surface px-3 py-2">
            <span className="select-none truncate text-xs text-primary-token blur-[3.5px]">{field.value}</span>
            <Lock className="ml-auto h-3 w-3 flex-none text-brand-500" />
          </div>
        </motion.div>
      ))}
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.9 }}>
        <div className="text-[10px] font-semibold uppercase tracking-wide text-muted-token">One-time code</div>
        <div className="mt-1 rounded-md border border-token bg-surface px-3 py-2 text-center font-mono text-xs font-bold tracking-[0.25em] text-brand-500">
          418 305
        </div>
      </motion.div>
      <motion.div
        initial={{ opacity: 0.4 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 1.3 }}
        className="rounded-md bg-brand-600 py-2 text-center text-[11px] font-bold text-white"
      >
        Signing in…
      </motion.div>
    </div>
  );
}

/* -- 4. Through, with nothing left behind that a person could read. ------------------------ */
function SceneIn() {
  return (
    <div className="grid min-h-[230px] place-items-center rounded-lg border border-token bg-surface-2">
      <div className="text-center">
        <motion.span
          className="mx-auto grid h-11 w-11 place-items-center rounded-full bg-emerald-500/10"
          initial={{ scale: 0.7, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ type: "spring", stiffness: 220, damping: 16 }}
        >
          <CheckCircle2 className="h-6 w-6 text-emerald-500" />
        </motion.span>
        <p className="mt-3 text-xs font-semibold">Signed in to Northwind Portal</p>
        <p className="mx-auto mt-2 max-w-[15rem] text-[10px] leading-snug text-muted-token">
          They never saw the password, and they could not repeat it if they were asked.
        </p>
      </div>
    </div>
  );
}

/* -- 5. The half a shared password can never produce. ------------------------------------- */
function SceneRecord() {
  return (
    <div className="space-y-2">
      <div className="grid grid-cols-12 gap-2 px-1 text-[10px] font-medium uppercase tracking-wide text-muted-token">
        <div className="col-span-4">User</div>
        <div className="col-span-3">Portal</div>
        <div className="col-span-5 text-right">From</div>
      </div>
      {[
        { user: "r•••t@company.com", portal: "Lakeside VMS", from: "203.0.113.18 · Edge", fresh: false },
        { user: "m•••a@company.com", portal: "Redwood Staffing", from: "198.51.100.7 · Firefox", fresh: false },
      ].map((entry) => (
        <div key={entry.user} className="grid grid-cols-12 items-center gap-2 rounded-lg border border-token bg-surface-2 px-3 py-2.5 opacity-60">
          <div className="col-span-4 truncate text-[11px] font-semibold">{entry.user}</div>
          <div className="col-span-3 truncate text-[11px] text-secondary-token">{entry.portal}</div>
          <div className="col-span-5 text-right text-[10px] text-muted-token">{entry.from}</div>
        </div>
      ))}
      <motion.div
        initial={{ opacity: 0, y: -12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.25 }}
        className="grid grid-cols-12 items-center gap-2 rounded-lg border border-brand-500/50 bg-brand-500/5 px-3 py-2.5"
      >
        <div className="col-span-4 truncate text-[11px] font-semibold">a•••a@company.com</div>
        <div className="col-span-3 truncate text-[11px] text-secondary-token">Northwind Portal</div>
        <div className="col-span-5 text-right text-[10px] text-muted-token">203.0.113.41 · Chrome</div>
      </motion.div>
      <p className="flex items-center gap-1.5 pt-1 text-[10px] text-muted-token">
        <ShieldCheck className="h-3 w-3 text-brand-500" /> Written to the audit log as it happens.
      </p>
    </div>
  );
}
