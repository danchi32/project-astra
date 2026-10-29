"use client";

import { AnimatePresence, motion } from "framer-motion";
import { Bell, Check, ChevronLeft, Search, Signal, BatteryFull, Wifi } from "lucide-react";
import type { AppDemo, AppScreen } from "@/lib/services";
import { cn } from "@/lib/utils";

const tone = {
  ok: "bg-emerald-500/15 text-emerald-600",
  warn: "bg-amber-500/15 text-amber-600",
  info: "bg-blue-500/15 text-blue-600",
};

function Screen({ s, app }: { s: AppScreen; app: AppDemo }) {
  const grad = { background: `linear-gradient(135deg, ${app.from}, ${app.to})` };
  switch (s.kind) {
    case "stats":
      return (
        <div>
          <div className="rounded-b-3xl px-5 pb-6 pt-4 text-white" style={grad}>
            <div className="flex items-center justify-between">
              <span className="text-lg font-bold">{s.title}</span>
              <Bell className="h-4 w-4" />
            </div>
            <div className="mt-1 text-xs opacity-85">{s.greeting}</div>
            <div className="mt-4 grid grid-cols-2 gap-2">
              {s.cards.map((c) => (
                <div key={c.label} className="rounded-xl bg-white/20 p-3 backdrop-blur">
                  <div className="text-xl font-bold">{c.value}</div>
                  <div className="text-[10px] opacity-85">{c.label}</div>
                </div>
              ))}
            </div>
          </div>
          <div className="mx-4 -mt-3 rounded-2xl bg-white p-3 shadow-md">
            <div className="flex h-16 items-end gap-1.5">
              {s.bars.map((h, i) => (
                <motion.div
                  key={i}
                  className="flex-1 rounded-t"
                  style={{ ...grad, opacity: 0.85 }}
                  initial={{ height: 0 }}
                  animate={{ height: `${h}%` }}
                  transition={{ delay: 0.1 + i * 0.05, duration: 0.5 }}
                />
              ))}
            </div>
          </div>
          <div className="space-y-2 p-4">
            {s.rows.map((r) => (
              <div key={r.title} className="flex items-center justify-between rounded-xl bg-white p-3 shadow-sm">
                <div>
                  <div className="text-xs font-semibold text-slate-800">{r.title}</div>
                  <div className="text-[10px] text-slate-500">{r.sub}</div>
                </div>
                {r.badge && <span className="rounded-full px-2 py-0.5 text-[9px] font-bold text-white" style={grad}>{r.badge}</span>}
              </div>
            ))}
          </div>
        </div>
      );
    case "list":
      return (
        <div className="p-4">
          <div className="text-lg font-bold text-slate-900">{s.title}</div>
          {s.search && (
            <div className="mt-3 flex items-center gap-2 rounded-xl bg-slate-100 px-3 py-2 text-[11px] text-slate-400">
              <Search className="h-3.5 w-3.5" /> {s.search}
            </div>
          )}
          <div className="mt-3 space-y-2">
            {s.rows.map((r, i) => (
              <motion.div
                key={r.title}
                initial={{ opacity: 0, x: 16 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.07 }}
                className="flex items-center gap-3 rounded-xl bg-white p-3 shadow-sm"
              >
                <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg text-xs font-bold text-white" style={grad}>
                  {r.title.replace(/[^A-Za-z]/g, "").slice(0, 1)}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="truncate text-xs font-semibold text-slate-800">{r.title}</div>
                  <div className="truncate text-[10px] text-slate-500">{r.sub}</div>
                </div>
                {r.badge && (
                  <span className={cn("shrink-0 rounded-full px-2 py-0.5 text-[9px] font-bold", tone[r.tone ?? "info"])}>{r.badge}</span>
                )}
              </motion.div>
            ))}
          </div>
        </div>
      );
    case "slots":
      return (
        <div className="p-4">
          <div className="flex items-center gap-2 text-slate-900">
            <ChevronLeft className="h-4 w-4" />
            <span className="text-lg font-bold">{s.title}</span>
          </div>
          <div className="mt-1 text-[11px] text-slate-500">{s.subtitle}</div>
          <div className="mt-4 grid grid-cols-4 gap-2">
            {s.days.map((d, i) => (
              <div
                key={d}
                className={cn("rounded-xl py-2 text-center text-[10px] font-semibold", i === 1 ? "text-white" : "bg-white text-slate-600 shadow-sm")}
                style={i === 1 ? grad : undefined}
              >
                {d}
              </div>
            ))}
          </div>
          <div className="mt-4 grid grid-cols-3 gap-2">
            {s.slots.map((t, i) => (
              <motion.div
                key={t}
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: i * 0.04 }}
                className={cn(
                  "rounded-lg border py-2 text-center text-[11px] font-medium",
                  i === 2 ? "border-transparent text-white" : "border-slate-200 bg-white text-slate-600",
                  i === 5 && "opacity-40 line-through",
                )}
                style={i === 2 ? grad : undefined}
              >
                {t}
              </motion.div>
            ))}
          </div>
          <div className="mt-6 rounded-xl py-3 text-center text-xs font-bold text-white" style={grad}>
            {s.button}
          </div>
        </div>
      );
    case "steps":
      return (
        <div className="p-4">
          <div className="flex items-center gap-2 text-slate-900">
            <ChevronLeft className="h-4 w-4" />
            <span className="truncate text-lg font-bold">{s.title}</span>
          </div>
          <div className="mt-1 text-[11px] text-slate-500">{s.subtitle}</div>
          <div className="mt-5 space-y-0 rounded-2xl bg-white p-4 shadow-sm">
            {s.steps.map((st, i) => (
              <motion.div
                key={st.label}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.1 }}
                className="flex gap-3"
              >
                <div className="flex flex-col items-center">
                  <span
                    className={cn("grid h-6 w-6 place-items-center rounded-full", st.done ? "text-white" : "border-2 border-slate-200 bg-white")}
                    style={st.done ? grad : undefined}
                  >
                    {st.done && <Check className="h-3.5 w-3.5" />}
                  </span>
                  {i < s.steps.length - 1 && <span className="h-7 w-0.5 bg-slate-200" />}
                </div>
                <div className="flex flex-1 justify-between pt-0.5">
                  <span className={cn("text-xs font-semibold", st.done ? "text-slate-800" : "text-slate-400")}>{st.label}</span>
                  <span className="text-[10px] text-slate-500">{st.time}</span>
                </div>
              </motion.div>
            ))}
          </div>
          {s.button && (
            <div className="mt-5 rounded-xl py-3 text-center text-xs font-bold text-white" style={grad}>
              {s.button}
            </div>
          )}
        </div>
      );
    case "grid":
      return (
        <div className="p-4">
          <div className="text-lg font-bold text-slate-900">{s.title}</div>
          <div className="relative mt-3 overflow-hidden rounded-2xl p-4 text-white" style={grad}>
            <div className="text-[10px] font-semibold uppercase opacity-85">Limited time</div>
            <div className="mt-1 text-sm font-bold">{s.banner}</div>
            <div className="absolute -right-4 -top-4 h-16 w-16 rounded-full bg-white/20" />
          </div>
          <div className="mt-3 grid grid-cols-2 gap-2">
            {s.items.map((it, i) => (
              <motion.div
                key={it.name}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.07 }}
                className="rounded-xl bg-white p-2 shadow-sm"
              >
                <div className="h-16 rounded-lg" style={{ ...grad, opacity: 0.25 + i * 0.15 }} />
                <div className="mt-2 text-[11px] font-semibold text-slate-800">{it.name}</div>
                <div className="text-[11px] font-bold" style={{ color: app.from }}>
                  {it.price}
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      );
  }
}

/** A phone showing one of the demo apps, with a working bottom tab bar. */
export function PhoneMockup({ app, tab, onTab }: { app: AppDemo; tab: number; onTab: (i: number) => void }) {
  const Icon = app.icon;
  return (
    <div className="relative mx-auto w-[290px] rounded-[2.8rem] border-[9px] border-neutral-900 bg-neutral-900 shadow-2xl shadow-brand-600/20">
      <div className="relative h-[580px] overflow-hidden rounded-[2.2rem] bg-slate-50">
        {/* Status bar */}
        <div className="flex items-center justify-between px-6 pt-3 text-[10px] font-semibold text-slate-800">
          <span>9:41</span>
          <span className="absolute left-1/2 top-2 h-5 w-24 -translate-x-1/2 rounded-full bg-black" />
          <span className="flex items-center gap-1">
            <Signal className="h-3 w-3" /> <Wifi className="h-3 w-3" /> <BatteryFull className="h-3.5 w-3.5" />
          </span>
        </div>
        <div className="h-[490px] overflow-hidden pt-2">
          <AnimatePresence mode="wait">
            <motion.div
              key={`${app.slug}-${tab}`}
              initial={{ opacity: 0, x: 30 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -30 }}
              transition={{ duration: 0.3 }}
            >
              <Screen s={app.screens[tab]} app={app} />
            </motion.div>
          </AnimatePresence>
        </div>
        {/* Tab bar */}
        <div className="absolute inset-x-0 bottom-0 flex border-t border-slate-200 bg-white px-2 pb-4 pt-2">
          {app.tabs.map((label, i) => (
            <button
              key={label}
              type="button"
              onClick={() => onTab(i)}
              className="flex flex-1 flex-col items-center gap-1 text-[10px] font-semibold"
              style={{ color: i === tab ? app.from : "#94a3b8" }}
            >
              {i === 0 ? <Icon className="h-4 w-4" /> : <span className="h-4 w-4 rounded-md border-2" style={{ borderColor: i === tab ? app.from : "#cbd5e1" }} />}
              {label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
