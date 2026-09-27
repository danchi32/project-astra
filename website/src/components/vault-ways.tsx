"use client";

import { motion } from "framer-motion";
import { ArrowRight, Lock, Puzzle, Search, ShieldCheck } from "lucide-react";

/**
 * The three places a portal sign-in can start. They matter to a buyer because they decide how
 * much anybody has to change: the vault is a page you already have open, the extension is one
 * click from the toolbar, and the third is for people who reached the portal by their own
 * bookmark and were never going to come through either of the first two.
 */

function Panel({ title, note, children }: { title: string; note: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col overflow-hidden rounded-2xl border border-token bg-surface shadow-xl">
      <div className="flex items-center gap-2 border-b border-token bg-surface-2 px-4 py-3">
        <span className="h-2.5 w-2.5 rounded-full bg-red-400/80" />
        <span className="h-2.5 w-2.5 rounded-full bg-amber-400/80" />
        <span className="h-2.5 w-2.5 rounded-full bg-emerald-400/80" />
        <span className="ml-2 truncate text-[11px] font-medium text-muted-token">{title}</span>
      </div>
      <div className="flex-1 p-4">{children}</div>
      <p className="border-t border-token px-4 py-3 text-[11px] leading-relaxed text-secondary-token">{note}</p>
    </div>
  );
}

/* -- 1. From the vault itself: the dashboard everyone is given. --------------------------- */
export function WayFromVault() {
  return (
    <Panel title="vault.technomateai.com" note="Sign in to the vault, and every portal assigned to you is on one page.">
      <div className="space-y-2">
        {[
          { name: "Northwind Portal", letter: "N", lead: true },
          { name: "Lakeside VMS", letter: "L", lead: false },
        ].map((portal, index) => (
          <motion.div
            key={portal.name}
            initial={{ opacity: 0, x: -10 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            transition={{ delay: index * 0.12 }}
            className={`flex items-center gap-2.5 rounded-lg border px-3 py-2.5 ${portal.lead ? "border-brand-500/50 bg-brand-500/5" : "border-token bg-surface-2"}`}
          >
            <span className="grid h-8 w-8 flex-none place-items-center rounded-lg bg-brand-500/10 text-xs font-bold text-brand-500">{portal.letter}</span>
            <div className="min-w-0 flex-1">
              <div className="truncate text-xs font-semibold">{portal.name}</div>
              <div className="flex items-center gap-1 text-[10px] text-muted-token">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" /> Credentials protected
              </div>
            </div>
            <span className="flex flex-none items-center gap-1 rounded-md bg-brand-600 px-2 py-1 text-[10px] font-bold text-white">
              Open <ArrowRight className="h-3 w-3" />
            </span>
          </motion.div>
        ))}
      </div>
    </Panel>
  );
}

/* -- 2. From the toolbar, without leaving whatever they were doing. ----------------------- */
export function WayFromExtension() {
  return (
    <Panel title="Extension — toolbar" note="One click from the toolbar, on any tab, without opening the vault at all.">
      <div className="mx-auto w-full max-w-[15rem] rounded-xl border border-token bg-surface-2 p-2.5">
        <div className="mb-2 flex items-center gap-2 border-b border-token pb-2">
          <span className="grid h-5 w-5 flex-none place-items-center rounded bg-brand-600 text-[9px] font-black text-white">V</span>
          <span className="text-[10px] font-bold">Secure Vault</span>
          <Puzzle className="ml-auto h-3 w-3 text-muted-token" />
        </div>
        <div className="flex items-center gap-1.5 rounded-md border border-token bg-surface px-2 py-1.5">
          <Search className="h-3 w-3 flex-none text-muted-token" />
          <span className="text-[10px] text-muted-token">Search logins</span>
        </div>
        <div className="mt-2 space-y-1.5">
          {["Northwind Portal", "Lakeside VMS", "Redwood Systems"].map((name, index) => (
            <motion.div
              key={name}
              initial={{ opacity: 0 }}
              whileInView={{ opacity: 1 }}
              viewport={{ once: true }}
              transition={{ delay: 0.15 + index * 0.1 }}
              className="flex items-center gap-2 rounded-md px-2 py-1.5 text-[10px] font-semibold hover:bg-surface"
            >
              <Lock className="h-3 w-3 flex-none text-brand-500" />
              <span className="truncate">{name}</span>
            </motion.div>
          ))}
        </div>
      </div>
    </Panel>
  );
}

/* -- 3. Already on the portal, by their own bookmark. ------------------------------------ */
export function WayOnThePage() {
  return (
    <Panel title="northwind.example.com/login" note="Already on the portal? The vault offers the login that belongs to that site, and fills it there.">
      <div className="space-y-2">
        <div className="text-[10px] font-semibold uppercase tracking-wide text-muted-token">Username</div>
        <div className="flex items-center gap-2 rounded-md border border-brand-500/50 bg-surface-2 px-3 py-2">
          <span className="text-[11px] text-muted-token">Sign in to Northwind</span>
          <motion.span
            initial={{ scale: 0.6, opacity: 0 }}
            whileInView={{ scale: 1, opacity: 1 }}
            viewport={{ once: true }}
            transition={{ delay: 0.2, type: "spring", stiffness: 240, damping: 15 }}
            className="ml-auto grid h-5 w-5 flex-none place-items-center rounded bg-brand-600 text-[9px] font-black text-white"
          >
            V
          </motion.span>
        </div>
        <motion.div
          initial={{ opacity: 0, y: -8 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ delay: 0.45 }}
          className="rounded-lg border border-token bg-surface-2 p-2"
        >
          {["a•••••n@company.com", "o•••s@company.com"].map((user) => (
            <div key={user} className="flex items-center gap-2 rounded-md px-2 py-1.5 text-[10px] font-semibold">
              <Lock className="h-3 w-3 flex-none text-brand-500" />
              <span className="truncate">{user}</span>
            </div>
          ))}
          <p className="flex items-center gap-1.5 px-2 pt-1 text-[9px] text-muted-token">
            <ShieldCheck className="h-3 w-3 flex-none text-brand-500" /> Names only, drawn where the site cannot read it
          </p>
        </motion.div>
      </div>
    </Panel>
  );
}
