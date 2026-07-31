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
  features: string[];
};

/**
 * Feature-based tiers, priced per device. A line ending in "plus:" renders as
 * a sub-heading (no tick) so the cumulative structure reads clearly.
 */
const TIERS: Tier[] = [
  {
    id: "essential",
    name: "Essential",
    tagline: "Know and control every device you own.",
    cta: "Start free trial",
    features: [
      "Device inventory & asset tracking",
      "Live telemetry — CPU, RAM, disk, events",
      "Patch management — push Windows Updates",
      "AI assistant — diagnosis & guidance",
      "Reporting & dashboards",
      "Email support",
    ],
  },
  {
    id: "professional",
    name: "Professional",
    tagline: "Let the AI fix issues, not just find them.",
    featured: true,
    cta: "Start free trial",
    features: [
      "Everything in Essential, plus:",
      "AI Cognitive Engine — automatic self-healing",
      "Approval tiers — automatic, approval, admin-only",
      "Secure offboarding & device lock-down",
      "Conversational AI resolution for employees",
      "Notifications & proactive alerts",
      "Priority support",
    ],
  },
  {
    id: "expert",
    name: "Expert",
    tagline: "Compliance and fleet-wide control at scale.",
    cta: "Start free trial",
    features: [
      "Everything in Professional, plus:",
      "Compliance & security posture dashboard",
      "Restricted-software detection",
      "Fleet cross-device correlation",
      "One-click mass remediation",
      "Full audit trail & export",
      "Advanced RBAC & SSO",
      "Dedicated success manager",
    ],
  },
];

type Price = { monthly: number | null; annual: number | null };
type Prices = Record<string, Price>;

// Defaults — overridden at runtime by /pricing.json (editable on the server).
const DEFAULT_PRICES: Prices = {
  essential: { monthly: 4.49, annual: 44.9 },
  professional: { monthly: 5.99, annual: 59.9 },
  expert: { monthly: 8.99, annual: 89.9 },
};

/** 5.99 → "5.99", 45 → "45" (keeps clean whole numbers whole). */
const fmt = (n: number) => (Number.isInteger(n) ? String(n) : n.toFixed(2));

export function PricingPlans() {
  const { c, list } = useContent();
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
  const feat = priceOf("professional");
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
        {TIERS.map((tier) => {
          const p = priceOf(tier.id);
          const amount = annual ? p.annual : p.monthly;
          const features = list<string>(
            `pricing.tiers.${tier.id}.features`,
            tier.features,
          );
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
                  {c("pricing.featuredLabel", "Most popular")}
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
                    <span className="text-4xl font-extrabold">
                      ${fmt(amount)}
                    </span>
                    <span className="text-sm text-muted-token">
                      /device&nbsp;/{annual ? "yr" : "mo"}
                    </span>
                  </div>
                )}
                <p className="mt-1 text-xs text-muted-token">
                  {amount === null
                    ? "Tailored to your fleet"
                    : annual
                      ? "billed annually, per device"
                      : "billed monthly, per device"}
                </p>
              </div>

              <a
                href={site.appUrl}
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
                {features.map((f) => {
                  const isHeader = f.trim().endsWith("plus:");
                  return (
                    <li
                      key={f}
                      className={cn(
                        "flex items-start gap-2.5 text-sm",
                        isHeader
                          ? "font-semibold text-primary-token"
                          : "text-secondary-token",
                      )}
                    >
                      {!isHeader && (
                        <Check className="mt-0.5 h-4 w-4 shrink-0 text-emerald-500" />
                      )}
                      <span className={isHeader ? "pt-1" : ""}>{f}</span>
                    </li>
                  );
                })}
              </ul>
            </div>
          );
        })}
      </div>

      {/* Volume / bulk strip */}
      <div className="mt-8 flex flex-col items-center justify-between gap-4 rounded-2xl border border-token bg-surface px-6 py-5 sm:flex-row">
        <div>
          <h3 className="text-base font-bold">
            {c("pricing.bulk.title", "More than 50 devices?")}
          </h3>
          <p className="mt-1 text-sm text-secondary-token">
            {c(
              "pricing.bulk.desc",
              "Talk to us about volume pricing, guided rollout and custom requirements.",
            )}
          </p>
        </div>
        <a
          href="/contact/"
          className="inline-flex shrink-0 items-center gap-2 rounded-xl border border-token bg-app px-5 py-3 text-sm font-semibold transition-all hover:border-brand-500/50"
        >
          {c("pricing.bulk.cta", "Contact sales")}{" "}
          <ArrowRight className="h-4 w-4" />
        </a>
      </div>

      <p className="mt-8 text-center text-xs text-muted-token">
        {c("pricing.note", "All prices are per device. Taxes may apply.")}
      </p>
    </div>
  );
}
