"use client";

import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { CheckCircle2, ShieldCheck, Activity } from "lucide-react";
import { SavioMark } from "@/components/SavioMark";

/**
 * Floating cards around the hero's 3D core: SAVIO visibly at work.
 *
 * Every line here is an example of what the product does — the reasoning loop, an automatic
 * fix, an approval-tier hold, a telemetry reading — never a count or a rate. The site does not
 * print numbers it has not measured (see the comment on the stats block in HomeContent).
 */
const LOOP = [
  "Understanding the request…",
  "Searching the knowledge base…",
  "Collecting live telemetry…",
  "Applying an approved fix…",
  "Verified — issue resolved",
];

function Chip({ className, delay, children }: { className: string; delay: number; children: React.ReactNode }) {
  return (
    <motion.div
      className={`glass absolute z-10 rounded-2xl border border-token px-3.5 py-2.5 shadow-xl ${className}`}
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: [0, -8, 0] }}
      transition={{
        opacity: { delay, duration: 0.5 },
        y: { delay, duration: 6, repeat: Infinity, ease: "easeInOut" },
      }}
    >
      {children}
    </motion.div>
  );
}

export function AgentActivity() {
  const [step, setStep] = useState(0);
  useEffect(() => {
    const id = window.setInterval(() => setStep((s) => (s + 1) % LOOP.length), 2200);
    return () => window.clearInterval(id);
  }, []);
  const done = step === LOOP.length - 1;

  return (
    <div aria-hidden className="pointer-events-none absolute inset-0 hidden sm:block">
      {/* The agent's live status: the reasoning loop, step by step. */}
      <Chip className="left-0 top-[8%] w-60" delay={0.4}>
        <div className="flex items-center gap-2.5">
          <SavioMark size={30} />
          <div className="min-w-0">
            <p className="text-xs font-bold tracking-wide">SAVIO</p>
            <AnimatePresence mode="wait">
              <motion.p
                key={step}
                className={`truncate text-[11px] ${done ? "text-emerald-500 font-semibold" : "text-secondary-token"}`}
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.25 }}
              >
                {LOOP[step]}
              </motion.p>
            </AnimatePresence>
          </div>
        </div>
      </Chip>

      <Chip className="right-0 top-[38%]" delay={0.9}>
        <div className="flex items-center gap-2 text-xs">
          <CheckCircle2 className="h-4 w-4 text-emerald-500" />
          <div>
            <p className="font-semibold">Outlook restarted</p>
            <p className="text-[11px] text-muted-token">Automatic tier · verified</p>
          </div>
        </div>
      </Chip>

      <Chip className="bottom-[10%] left-[4%]" delay={1.4}>
        <div className="flex items-center gap-2 text-xs">
          <ShieldCheck className="h-4 w-4 text-amber-500" />
          <div>
            <p className="font-semibold">Network reset</p>
            <p className="text-[11px] text-muted-token">Waiting for admin approval</p>
          </div>
        </div>
      </Chip>

      <Chip className="bottom-[2%] right-[8%]" delay={1.9}>
        <div className="flex items-center gap-2 text-xs">
          <Activity className="h-4 w-4 text-cyan-500" />
          <div>
            <p className="font-semibold">Live telemetry</p>
            <p className="text-[11px] text-muted-token">CPU · RAM · disk · events</p>
          </div>
        </div>
      </Chip>
    </div>
  );
}
