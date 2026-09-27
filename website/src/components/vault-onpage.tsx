"use client";

import { AnimatePresence, motion } from "framer-motion";
import { CheckCircle2, Lock, MousePointer2 } from "lucide-react";
import { useEffect, useState } from "react";

/**
 * The third way in, played out on a whole page rather than described.
 *
 * Somebody reached the portal by their own bookmark. They never opened the vault and never
 * touched the toolbar, and this is the sequence that still signs them in: the badge appears
 * in the field, the picker offers the accounts that belong to that site, and a click fills
 * and submits. Every frame is markup, so it follows the visitor's theme and leaves real text
 * behind.
 */

/* Each step holds for its own beat — a cursor move needs longer than a badge appearing. */
const STEPS = [900, 900, 800, 1100, 900, 1200, 1400, 1800] as const;
const [PAGE, TO_FIELD, BADGE, PICKER, TO_ACCOUNT, FILLED, COVER, DONE] = [0, 1, 2, 3, 4, 5, 6, 7];

export function OnPageSignIn() {
  const [step, setStep] = useState(PAGE);
  const [playing, setPlaying] = useState(true);

  useEffect(() => {
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    if (query.matches) setPlaying(false);
  }, []);

  useEffect(() => {
    if (!playing) return;
    const timer = setTimeout(() => setStep((value) => (value + 1) % STEPS.length), STEPS[step]);
    return () => clearTimeout(timer);
  }, [playing, step]);

  // Where the pointer is for this beat, in percentages of the panel.
  const cursor =
    step < TO_FIELD ? { left: "84%", top: "88%" }
    : step < TO_ACCOUNT ? { left: "76%", top: "44%" }
    : step < FILLED ? { left: "70%", top: "60%" }
    : { left: "76%", top: "82%" };

  const filling = step >= FILLED;

  return (
    <div className="overflow-hidden rounded-2xl border border-token bg-surface shadow-2xl">
      {/* Browser chrome — the point is that this is the portal's own site, not ours. */}
      <div className="flex items-center gap-2 border-b border-token bg-surface-2 px-4 py-3">
        <span className="h-3 w-3 rounded-full bg-red-400/80" />
        <span className="h-3 w-3 rounded-full bg-amber-400/80" />
        <span className="h-3 w-3 rounded-full bg-emerald-400/80" />
        <span className="ml-2 flex-1 truncate rounded-md bg-surface px-2.5 py-1 text-[10px] text-muted-token">
          northwind.example.com/login
        </span>
      </div>

      <div className="relative min-h-[300px] bg-surface-2 p-4">
        {/* The portal's own page: a header, some content, and its login card. */}
        <div className="flex items-center gap-2 border-b border-token pb-2.5">
          <span className="grid h-5 w-5 place-items-center rounded bg-secondary-token/20 text-[9px] font-black text-secondary-token">N</span>
          <span className="text-[10px] font-bold text-secondary-token">Northwind Portal</span>
          <div className="ml-auto flex gap-2">
            {[10, 8, 9].map((width, index) => (
              <span key={index} className="h-1.5 rounded-full bg-secondary-token/20" style={{ width: `${width * 3}px` }} />
            ))}
          </div>
        </div>

        <div className="mt-3 grid grid-cols-12 gap-3">
          <div className="col-span-5 space-y-2 pt-1">
            <span className="block h-2.5 w-4/5 rounded bg-secondary-token/20" />
            <span className="block h-2.5 w-3/5 rounded bg-secondary-token/15" />
            <span className="mt-3 block h-1.5 w-full rounded bg-secondary-token/10" />
            <span className="block h-1.5 w-11/12 rounded bg-secondary-token/10" />
            <span className="block h-1.5 w-4/5 rounded bg-secondary-token/10" />
          </div>

          <div className="col-span-7">
            <div className="rounded-lg border border-token bg-surface p-3">
              <div className="text-[10px] font-bold">Sign in</div>

              {/* Username, with the vault's badge and its picker. */}
              <div className="mt-2.5">
                <div className="text-[9px] font-semibold uppercase tracking-wide text-muted-token">Username</div>
                <div className={`mt-1 flex items-center gap-2 rounded-md border px-2.5 py-1.5 transition-colors ${step >= BADGE && step < FILLED ? "border-brand-500/60" : "border-token"}`}>
                  {filling
                    ? <span className="select-none truncate text-[11px] text-primary-token blur-[3px]">a.morgan@company.com</span>
                    : <span className="text-[11px] text-muted-token">Your username</span>}
                  <AnimatePresence>
                    {step >= BADGE && (
                      <motion.span
                        initial={{ scale: 0.5, opacity: 0 }}
                        animate={{ scale: 1, opacity: 1 }}
                        exit={{ scale: 0.5, opacity: 0 }}
                        transition={{ type: "spring", stiffness: 260, damping: 16 }}
                        className="ml-auto grid h-4 w-4 flex-none place-items-center rounded bg-brand-600 text-[8px] font-black text-white"
                      >
                        V
                      </motion.span>
                    )}
                  </AnimatePresence>
                </div>

                <AnimatePresence>
                  {(step === PICKER || step === TO_ACCOUNT) && (
                    <motion.div
                      initial={{ opacity: 0, y: -6 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -6 }}
                      className="mt-1 rounded-md border border-token bg-surface-2 p-1.5 shadow-lg"
                    >
                      {["a•••••n@company.com", "o•••s@company.com"].map((user, index) => (
                        <div
                          key={user}
                          className={`flex items-center gap-1.5 rounded px-1.5 py-1 text-[10px] font-semibold ${index === 0 && step === TO_ACCOUNT ? "bg-brand-500/10 text-brand-500" : ""}`}
                        >
                          <Lock className="h-2.5 w-2.5 flex-none text-brand-500" />
                          <span className="truncate">{user}</span>
                        </div>
                      ))}
                      <p className="px-1.5 pt-1 text-[8px] text-muted-token">Names only — the site cannot read this</p>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>

              {/* Password. */}
              <div className="mt-2.5">
                <div className="text-[9px] font-semibold uppercase tracking-wide text-muted-token">Password</div>
                <div className="mt-1 flex items-center gap-2 rounded-md border border-token px-2.5 py-1.5">
                  {filling
                    ? <span className="select-none truncate text-[11px] text-primary-token blur-[3px]">Th3-P0rtal-Secret</span>
                    : <span className="text-[11px] text-muted-token">Your password</span>}
                  {filling && <Lock className="ml-auto h-3 w-3 flex-none text-brand-500" />}
                </div>
              </div>

              <div className={`mt-3 rounded-md py-1.5 text-center text-[10px] font-bold text-white transition-colors ${step >= COVER ? "bg-brand-500" : "bg-brand-600"}`}>
                {step >= COVER ? "Signing in…" : "Sign in"}
              </div>
            </div>
          </div>
        </div>

        {/* The cover screen, and then the portal on the other side of it. */}
        <AnimatePresence>
          {step === COVER && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="absolute inset-0 grid place-items-center bg-surface-2/95 backdrop-blur-[2px]"
            >
              <div className="text-center">
                <motion.span
                  className="mx-auto block h-7 w-7 rounded-full border-2 border-brand-500/25 border-t-brand-500"
                  animate={{ rotate: 360 }}
                  transition={{ repeat: Infinity, duration: 0.9, ease: "linear" }}
                />
                <p className="mt-3 text-[10px] font-bold tracking-[0.12em] text-brand-500">SECURE SIGN-IN IN PROGRESS…</p>
              </div>
            </motion.div>
          )}
          {step === DONE && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="absolute inset-0 grid place-items-center bg-surface-2"
            >
              <div className="text-center">
                <motion.span
                  className="mx-auto grid h-10 w-10 place-items-center rounded-full bg-emerald-500/10"
                  initial={{ scale: 0.7 }}
                  animate={{ scale: 1 }}
                  transition={{ type: "spring", stiffness: 220, damping: 15 }}
                >
                  <CheckCircle2 className="h-5 w-5 text-emerald-500" />
                </motion.span>
                <p className="mt-3 text-[11px] font-semibold">Signed in to Northwind Portal</p>
                <p className="mx-auto mt-1.5 max-w-[16rem] text-[10px] leading-snug text-muted-token">
                  They never opened the vault, and never saw the password.
                </p>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* The pointer, gliding between the beats. */}
        {step < COVER && (
          <motion.span
            className="pointer-events-none absolute z-10 text-brand-500"
            animate={cursor}
            transition={{ duration: 0.55, ease: "easeInOut" }}
          >
            <MousePointer2 className="h-4 w-4 fill-brand-500" />
            {step === TO_ACCOUNT && (
              <motion.span
                className="absolute -left-1.5 -top-1.5 block h-6 w-6 rounded-full border border-brand-500"
                initial={{ scale: 0.4, opacity: 0.9 }}
                animate={{ scale: 1.5, opacity: 0 }}
                transition={{ duration: 0.7, repeat: Infinity }}
              />
            )}
          </motion.span>
        )}
      </div>

      <button
        type="button"
        onClick={() => setPlaying((value) => !value)}
        className="w-full border-t border-token bg-surface-2 px-4 py-2 text-[10px] font-semibold text-muted-token transition-colors hover:text-brand-500"
      >
        {playing ? "Pause" : "Play"} · already on the portal, signed in without opening the vault
      </button>
    </div>
  );
}
