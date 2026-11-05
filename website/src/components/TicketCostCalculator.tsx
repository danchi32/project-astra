"use client";

import { useRef, useState } from "react";
import { ArrowRight } from "lucide-react";
import { Button } from "@/components/ui";
import { bookDemo } from "@/lib/site";
import { trackEvent } from "@/lib/analytics";

const inputCls =
  "w-full rounded-xl border border-token bg-app px-4 py-3 text-sm text-primary-token focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/30";

// Example values only — every one is the visitor's to replace. They are deliberately
// ordinary rather than flattering: a calculator that inflates the problem by default is
// a sales claim we cannot back, and the decision log says we make none.
const fields = [
  { key: "tickets", label: "IT tickets per month", hint: "All requests: 'slow PC', printer, Outlook, access…", min: 0, step: 10, def: 150 },
  { key: "itMinutes", label: "IT time per ticket (minutes)", hint: "Triage, remote session, fix, follow-up", min: 0, step: 5, def: 30 },
  { key: "downMinutes", label: "Employee time lost per ticket (minutes)", hint: "Waiting, or working around the problem", min: 0, step: 5, def: 45 },
  { key: "itRate", label: "IT staff cost per hour (₹)", hint: "Monthly CTC ÷ ~160 hours", min: 0, step: 50, def: 500 },
  { key: "empRate", label: "Employee cost per hour (₹)", hint: "Average monthly CTC ÷ ~160 hours", min: 0, step: 50, def: 400 },
  { key: "repeatPct", label: "Repetitive tickets (%)", hint: "Your estimate: the same few problems again and again", min: 0, max: 100, step: 5, def: 40 },
] as const;

type Key = (typeof fields)[number]["key"];
type Values = Record<Key, number>;

const inr = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 });
const num = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });

export function TicketCostCalculator() {
  const [v, setV] = useState<Values>(
    () => Object.fromEntries(fields.map((f) => [f.key, f.def])) as Values,
  );
  const tracked = useRef(false);

  function update(key: Key, raw: string) {
    const n = Math.max(0, Number(raw) || 0);
    setV((prev) => ({ ...prev, [key]: key === "repeatPct" ? Math.min(100, n) : n }));
    if (!tracked.current) {
      tracked.current = true;
      trackEvent("calculator_used", { calculator: "it_ticket_cost", page_path: window.location.pathname });
    }
  }

  const itHours = (v.tickets * v.itMinutes) / 60;
  const downHours = (v.tickets * v.downMinutes) / 60;
  const monthly = itHours * v.itRate + downHours * v.empRate;
  const yearly = monthly * 12;
  const perTicket = v.tickets > 0 ? monthly / v.tickets : 0;
  const share = v.repeatPct / 100;

  const results = [
    { label: "Cost per ticket", value: inr.format(perTicket) },
    { label: "IT hours per month", value: num.format(itHours) },
    { label: "Employee hours lost per month", value: num.format(downHours) },
    { label: "Monthly cost of tickets", value: inr.format(monthly) },
  ];

  return (
    <div className="grid gap-6 lg:grid-cols-5">
      <form
        className="rounded-2xl border border-token bg-surface p-6 sm:p-8 lg:col-span-3 lg:self-start"
        onSubmit={(e) => e.preventDefault()}
      >
        <div className="grid gap-5 sm:grid-cols-2">
          {fields.map((f) => (
            <div key={f.key}>
              <label htmlFor={f.key} className="mb-1.5 block text-xs font-medium text-secondary-token">
                {f.label}
              </label>
              <input
                id={f.key}
                type="number"
                inputMode="numeric"
                min={f.min}
                max={"max" in f ? f.max : undefined}
                step={f.step}
                value={v[f.key]}
                onChange={(e) => update(f.key, e.target.value)}
                className={inputCls}
              />
              <p className="mt-1 text-xs text-muted-token">{f.hint}</p>
            </div>
          ))}
        </div>
        <p className="mt-6 text-xs text-muted-token">
          The starting numbers are examples. Replace them with your own; nothing you type
          leaves this page.
        </p>
      </form>

      <div className="flex flex-col rounded-2xl border border-token bg-surface p-6 sm:p-8 lg:col-span-2" aria-live="polite">
        <p className="text-sm font-medium text-secondary-token">Your IT tickets cost about</p>
        <p className="mt-1 text-4xl font-bold tracking-tight text-brand-500">{inr.format(yearly)}</p>
        <p className="text-sm text-secondary-token">per year</p>

        <dl className="mt-6 space-y-3 border-t border-token pt-5">
          {results.map((r) => (
            <div key={r.label} className="flex items-baseline justify-between gap-4 text-sm">
              <dt className="text-secondary-token">{r.label}</dt>
              <dd className="font-semibold text-primary-token">{r.value}</dd>
            </div>
          ))}
        </dl>

        <div className="mt-6 rounded-xl bg-brand-500/10 p-4 text-sm">
          <p className="font-semibold text-primary-token">
            {inr.format(yearly * share)} a year goes on repetitive tickets
          </p>
          <p className="mt-1 text-secondary-token">
            That&apos;s {num.format(itHours * share)} hours of IT time every month on problems
            your team has already solved before.
          </p>
        </div>

        <div className="mt-6 flex flex-col gap-3">
          <Button href={bookDemo.href} external={bookDemo.external}>
            Get a free fleet assessment <ArrowRight className="h-4 w-4" />
          </Button>
          <Button href="/pilot/" variant="secondary">
            Try SAVIO on 10 devices, free
          </Button>
        </div>
      </div>
    </div>
  );
}
