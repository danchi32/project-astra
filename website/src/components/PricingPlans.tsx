"use client";

import { useEffect, useState } from "react";
import { Check, ArrowRight, Sparkles } from "lucide-react";
import { motion } from "framer-motion";
import { site } from "@/lib/site";
import { useContent } from "@/lib/content";
import { cn } from "@/lib/utils";

type Tier = {
  id: string;
  name: string;
  tagline: string;
  featured?: boolean;
  cta: string;
};

// Every tier lists the SAME features — only the user count and price differ.
const FEATURES = [
  "Asset inventory & live telemetry",
  "Conversational AI assistant",
  "Self-healing with all approval tiers",
  "Patch management — push Windows Updates",
  "Secure offboarding & device lock-down",
  "Reporting & dashboards",
  "Role-based access control & audit logs",
  "Notifications & proactive alerts",
  "Priority support",
];

const tiers: Tier[] = [
  {
    id: "upto50",
    name: "1–50 users",
    tagline: "For small teams getting started.",
    cta: "Start free trial",
  },
  {
    id: "over50",
    name: "51–500 users",
    tagline: "For growing organizations that scale.",
    featured: true,
    cta: "Start free trial",
  },
  {
    id: "bulk",
    name: "500+ users",
    tagline: "For large-scale or custom deployments.",
    cta: "Contact sales",
  },
];

type Price = { monthly: number | null; annual: number | null };
type Prices = Record<string, Price>;

// Defaults — overridden at runtime by /pricing.json (editable on the server).
const DEFAULT_PRICES: Prices = {
  upto50: { monthly: 5.99, annual: 60 },
  over50: { monthly: 4.49, annual: 45 },
  bulk: { monthly: null, annual: null },
};

export function PricingPlans() {
  const { c, list } = useContent();
  const features = list<string>("pricing.features", FEATURES);
  const [annual, setAnnual] = useState(false);
  const [prices, setPrices] = useState<Prices>(DEFAULT_PRICES);

  // Load prices from /pricing.json so they can be edited on the server
  // (Hostinger File Manager) without rebuilding the site.
  useEffect(() => {
    fetch("/pricing.json", { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (data && typeof data === "object") {
          setPrices((prev) => ({ ...prev, ...data }));
        }
      })
      .catch(() => {
        /* keep defaults */
      });
  }, []);

  const priceOf = (id: string): Price =>
    prices[id] ?? DEFAULT_PRICES[id] ?? { monthly: null, annual: null };

  // Annual savings % for the featured tier (kept accurate even if edited).
  const feat = priceOf("over50");
  const savePct =
    feat.monthly && feat.annual
      ? Math.round((1 - feat.annual / (feat.monthly * 12)) * 100)
      : 0;

  return (
    <div>
      {/* Billing toggle */}
      <div className="flex items-center justify-center gap-3">
        <span
          className={cn(
            "text-sm font-medium",
            !annual ? "text-primary-token" : "text-muted-token",
          )}
        >
          {c("pricing.toggleMonthly", "Monthly")}
        </span>
        <button
          type="button"
          role="switch"
          aria-checked={annual}
          onClick={() => setAnnual((v) => !v)}
          className="relative h-7 w-12 rounded-full border border-token bg-surface-2 transition-colors"
        >
          <motion.span
            layout
            className="absolute top-0.5 h-5 w-5 rounded-full bg-brand-600 shadow"
            animate={{ left: annual ? "26px" : "2px" }}
            transition={{ type: "spring", stiffness: 500, damping: 30 }}
          />
        </button>
        <span
          className={cn(
            "text-sm font-medium",
            annual ? "text-primary-token" : "text-muted-token",
          )}
        >
          {c("pricing.toggleAnnual", "Annual")}
          {savePct > 0 && (
            <span className="ml-1.5 rounded-full bg-emerald-500/10 px-2 py-0.5 text-xs font-semibold text-emerald-500">
              Save {savePct}%
            </span>
          )}
        </span>
      </div>

      {/* Cards */}
      <div className="mt-12 grid gap-6 lg:grid-cols-3">
        {tiers.map((tier) => {
          const p = priceOf(tier.id);
          const amount = annual ? p.annual : p.monthly;
          return (
            <div
              key={tier.id}
              className={cn(
                "relative flex flex-col rounded-2xl border bg-surface p-7 transition-all",
                tier.featured
                  ? "border-brand-500/60 shadow-xl shadow-brand-600/10 lg:-mt-4 lg:mb-4"
                  : "border-token hover:border-brand-500/30",
              )}
            >
              {tier.featured && (
                <span className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-brand-600 px-3 py-1 text-xs font-semibold text-white">
                  <Sparkles className="mr-1 inline h-3 w-3" />
                  {c("pricing.featuredLabel", "Best value")}
                </span>
              )}
              <h3 className="text-lg font-bold">
                {c(`pricing.tiers.${tier.id}.name`, tier.name)}
              </h3>
              <p className="mt-1.5 min-h-[40px] text-sm text-secondary-token">
                {c(`pricing.tiers.${tier.id}.tagline`, tier.tagline)}
              </p>

              <div className="mt-5">
                {amount === null ? (
                  <div className="text-3xl font-extrabold">Custom</div>
                ) : (
                  <div className="flex items-baseline gap-1">
                    <span className="text-4xl font-extrabold">${amount}</span>
                    <span className="text-sm text-muted-token">
                      /user&nbsp;/{annual ? "yr" : "mo"}
                    </span>
                  </div>
                )}
                <p className="mt-1 text-xs text-muted-token">
                  {amount === null
                    ? "Tailored to your team"
                    : annual
                      ? "billed annually, per user"
                      : "billed monthly, per user"}
                </p>
              </div>

              <a
                href={tier.id === "bulk" ? "/contact" : site.appUrl}
                className={cn(
                  "mt-6 inline-flex items-center justify-center gap-2 rounded-xl px-5 py-3 text-sm font-semibold transition-all",
                  tier.featured
                    ? "bg-brand-600 text-white shadow-lg shadow-brand-600/25 hover:bg-brand-500"
                    : "border border-token bg-app hover:border-brand-500/50",
                )}
              >
                {c(`pricing.tiers.${tier.id}.cta`, tier.cta)}{" "}
                <ArrowRight className="h-4 w-4" />
              </a>

              <ul className="mt-7 space-y-3">
                {features.map((f) => (
                  <li
                    key={f}
                    className="flex items-start gap-2.5 text-sm text-secondary-token"
                  >
                    <Check className="mt-0.5 h-4 w-4 shrink-0 text-emerald-500" />
                    <span>{f}</span>
                  </li>
                ))}
              </ul>
            </div>
          );
        })}
      </div>

      <p className="mt-8 text-center text-xs text-muted-token">
        {c("pricing.note", "All prices are per user. Taxes may apply.")}
      </p>
    </div>
  );
}
