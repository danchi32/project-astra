"use client";
import Link from "next/link";
import { Lock, ArrowRight } from "lucide-react";
import { FEATURE_LABELS } from "@/lib/api/types";

/** Which plan a feature belongs to, for the sentence shown to the user. Mirrors the
 *  backend's entitlements table; kept here rather than fetched because it is copy, not a
 *  decision — the server still owns whether the request is allowed. */
const FEATURE_PLAN: Record<string, string> = {
  ai_act: "Professional",
  approval_tiers: "Professional",
  lockdown: "Professional",
  employee_chat: "Professional",
  compliance: "Expert",
  banned_software: "Expert",
  fleet_correlation: "Expert",
  fleet_remediation: "Expert",
  audit_export: "Expert",
  advanced_rbac: "Expert",
};

/** True when a failed request was refused because of the org's plan rather than an error.
 *
 *  402 and not 403 on purpose: the user has the right role, their plan simply doesn't
 *  include this. Showing them "Insufficient permissions" would send them to their
 *  administrator, who also cannot help. */
export function isUpgradeRequired(e: unknown): boolean {
  return (e as { response?: { status?: number } })?.response?.status === 402;
}

/** The feature the server said was missing, from the header it sets on the 402. */
export function requiredFeature(e: unknown): string | null {
  const h = (e as { response?: { headers?: Record<string, string> } })?.response?.headers;
  return h?.["x-astra-required-feature"] ?? null;
}

/**
 * Shown in place of a page the org's plan doesn't include.
 *
 * The page stays in the nav and still opens. Hiding it would make ASTRA look like it lacks
 * the capability, which is the opposite of what an upgrade prompt is for — the point is that
 * the feature exists and is one plan away.
 */
export function UpgradeRequired({ feature }: { feature: string | null }) {
  const name = feature ? FEATURE_LABELS[feature] ?? null : null;
  const plan = feature ? FEATURE_PLAN[feature] : null;

  return (
    <div className="rounded-xl p-8 text-center max-w-lg mx-auto"
      style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
      <div className="inline-flex p-3 rounded-xl mb-3"
        style={{ background: "rgba(154,47,187,0.10)", color: "var(--accent)" }}>
        <Lock size={22} />
      </div>
      <h2 className="text-base font-semibold" style={{ color: "var(--text-primary)" }}>
        {name ? `${name} is part of ${plan ?? "a higher plan"}` : "This is part of a higher plan"}
      </h2>
      <p className="text-sm mt-2" style={{ color: "var(--text-secondary)" }}>
        Your organization&apos;s current plan doesn&apos;t include it. Nothing is missing from
        your data — the feature is switched on the moment the plan changes.
      </p>
      <Link href="/billing"
        className="inline-flex items-center gap-1.5 mt-5 px-4 py-2 rounded-lg text-sm font-medium text-white"
        style={{ background: "var(--accent)" }}>
        See plans <ArrowRight size={15} />
      </Link>
      <p className="text-xs mt-3" style={{ color: "var(--text-secondary)" }}>
        Talk to your ASTRA contact if you think this is wrong.
      </p>
    </div>
  );
}
