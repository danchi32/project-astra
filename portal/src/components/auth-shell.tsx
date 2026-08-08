"use client";
import type { ComponentType, ReactNode } from "react";
import {
  Activity,
  BrainCircuit,
  CreditCard,
  Layers,
  ScrollText,
  ShieldCheck,
  Sparkles,
} from "lucide-react";

/**
 * The frame every signed-out page sits in.
 *
 * These four pages were a form floating in an empty viewport, which reads as unfinished
 * rather than clean — someone arriving at the sign-in page had no way to tell what ASTRA
 * is. The left panel answers that while they type, and carries no interactive elements, so
 * it never competes with the form for attention.
 *
 * Everything on the left is a claim the product page already makes. Nothing here invents a
 * statistic, a customer, or a screenshot of a fleet that does not exist.
 */

type Point = { icon: ComponentType<{ size?: number }>; title: string; body: string };

/** What someone signing IN needs reminding of: what this product is. */
const PILLARS: Point[] = [
  {
    icon: BrainCircuit,
    title: "Evidence before action",
    body: "Understands the request, searches your knowledge base and collects live telemetry — before it proposes a single fix.",
  },
  {
    icon: ShieldCheck,
    title: "You decide what runs unattended",
    body: "Automatic, approval-required and admin-only tiers, enforced in code rather than asked for in a prompt.",
  },
  {
    icon: ScrollText,
    title: "Every action is on the record",
    body: "Each mutation and each command sent to a device is logged, attributable and reviewable.",
  },
];

/**
 * What someone signing UP needs answered: what does this cost me to try?
 *
 * All four claims are true of the code as it stands, not aspirational marketing:
 * `TRIAL_DAYS = 14` (backend/app/services/subscription.py), the signup form asks for no
 * payment details, `TRIAL_PLAN = EXPERT` (backend/app/services/entitlements.py) so a trial
 * really is the top tier, and an expired trial goes read-only rather than billing anyone.
 * If any of those change, this copy is a lie and has to change with them.
 */
export const TRIAL_POINTS: Point[] = [
  {
    icon: CreditCard,
    title: "No credit card to start",
    body: "Sign up with a work email. We ask for payment details when you decide to buy, not before.",
  },
  {
    icon: Layers,
    title: "The whole product for 14 days",
    body: "Not a cut-down tier — your trial runs on the top plan, so you evaluate what you'd actually be buying.",
  },
  {
    icon: Sparkles,
    title: "Nothing happens automatically at the end",
    body: "No card on file means nothing to charge. If the trial lapses, your data stays and the account turns read-only until you upgrade.",
  },
];

/** The reasoning loop, in the product's own words. Rendered rather than screenshotted:
 *  a mocked-up dashboard would be a picture of a fleet nobody owns. */
const LOOP = ["Understand", "Search knowledge", "Collect evidence", "Fix", "Verify"];

export function AuthShell({
  children,
  subtitle,
  eyebrow,
  headline = "An AI system administrator for your Windows fleet.",
  blurb = "ASTRA watches every device, works out what is actually wrong, and fixes it — with a human in the loop wherever that matters.",
  points = PILLARS,
}: {
  children: ReactNode;
  /** What this particular page is for — sits under the wordmark on small screens. */
  subtitle: string;
  /** Optional badge above the headline, for the one thing worth reading first. */
  eyebrow?: string;
  headline?: string;
  blurb?: string;
  points?: Point[];
}) {
  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[1.05fr_minmax(420px,0.95fr)]"
      style={{ background: "var(--bg)" }}>

      {/* Left: what this is. Hidden below lg — on a phone the form is the whole job, and a
          wall of prose above it would push the fields off the first screen. */}
      <aside className="hidden lg:flex flex-col justify-between p-12 xl:p-16 relative overflow-hidden"
        style={{ background: "var(--surface)", borderRight: "1px solid var(--border)" }}>

        {/* Two soft accent washes. Kept at low alpha off var(--accent) so they read the same
            way in both themes instead of being a light-mode-only flourish. */}
        <div aria-hidden className="pointer-events-none absolute -top-32 -left-24 w-[28rem] h-[28rem] rounded-full blur-3xl"
          style={{ background: "color-mix(in srgb, var(--accent) 18%, transparent)" }} />
        <div aria-hidden className="pointer-events-none absolute -bottom-40 -right-16 w-[26rem] h-[26rem] rounded-full blur-3xl"
          style={{ background: "color-mix(in srgb, var(--accent) 12%, transparent)" }} />

        <div className="relative">
          <div className="inline-flex items-center gap-2 text-2xl font-bold" style={{ color: "var(--accent)" }}>
            <span className="text-3xl">⬡</span> ASTRA
          </div>
          <p className="mt-1 text-sm" style={{ color: "var(--text-secondary)" }}>
            AI Operations Platform
          </p>
        </div>

        <div className="relative max-w-lg">
          {eyebrow && (
            <span className="inline-block mb-4 px-3 py-1 rounded-full text-xs font-semibold tracking-wide"
              style={{
                background: "color-mix(in srgb, var(--accent) 14%, transparent)",
                color: "var(--accent)",
              }}>
              {eyebrow}
            </span>
          )}
          <h1 className="text-3xl xl:text-4xl font-semibold leading-tight tracking-tight"
            style={{ color: "var(--text-primary)" }}>
            {headline}
          </h1>
          <p className="mt-4 text-base leading-relaxed" style={{ color: "var(--text-secondary)" }}>
            {blurb}
          </p>

          <ul className="mt-10 space-y-6">
            {points.map(({ icon: Icon, title, body }) => (
              <li key={title} className="flex gap-4">
                <span className="shrink-0 mt-0.5 p-2 rounded-lg h-fit"
                  style={{ background: "color-mix(in srgb, var(--accent) 12%, transparent)", color: "var(--accent)" }}>
                  <Icon size={18} />
                </span>
                <div>
                  <p className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>{title}</p>
                  <p className="text-sm mt-1 leading-relaxed" style={{ color: "var(--text-secondary)" }}>{body}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>

        <div className="relative">
          <p className="text-xs font-medium uppercase tracking-wider flex items-center gap-1.5"
            style={{ color: "var(--text-secondary)" }}>
            <Activity size={13} /> How a fix happens
          </p>
          <div className="mt-3 flex flex-wrap items-center gap-x-2 gap-y-2">
            {LOOP.map((step, i) => (
              <span key={step} className="flex items-center gap-2">
                <span className="px-2.5 py-1 rounded-md text-xs font-medium"
                  style={{
                    background: "var(--bg)",
                    border: "1px solid var(--border)",
                    color: "var(--text-primary)",
                  }}>
                  {step}
                </span>
                {i < LOOP.length - 1 && (
                  <span aria-hidden style={{ color: "var(--text-secondary)" }}>→</span>
                )}
              </span>
            ))}
          </div>
        </div>
      </aside>

      {/* Right: the form, and nothing else. */}
      <main className="flex items-center justify-center p-6 py-12 lg:p-12">
        <div className="w-full max-w-sm">
          {/* The wordmark repeats here only where the left panel is gone, so large screens
              don't show it twice. */}
          <div className="lg:hidden mb-8 text-center">
            <div className="inline-flex items-center gap-2 text-2xl font-bold" style={{ color: "var(--accent)" }}>
              <span className="text-3xl">⬡</span> ASTRA
            </div>
            <p className="mt-1 text-sm" style={{ color: "var(--text-secondary)" }}>{subtitle}</p>
          </div>
          {children}
        </div>
      </main>
    </div>
  );
}

/** Shared field styling, so the four auth forms cannot drift apart. */
export const authInputCls =
  "w-full px-3 py-2.5 rounded-lg text-sm outline-none focus:ring-2 focus:ring-brand-500";
export const authInputStyle = {
  background: "var(--bg)",
  border: "1px solid var(--border)",
  color: "var(--text-primary)",
} as const;
export const authLabelCls = "block text-sm font-medium mb-1.5";
export const authButtonCls =
  "w-full py-2.5 rounded-lg text-sm font-semibold text-white transition-opacity disabled:opacity-50";
