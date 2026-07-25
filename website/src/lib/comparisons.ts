/**
 * Data for the /compare/[slug] landing pages (ASTRA vs <competitor>).
 *
 * Positioning is deliberately HONEST and balanced: some rows favour Astra, some
 * favour the competitor. Balanced comparisons are more credible, convert better,
 * and are legally safer than one-sided "we win everything" tables.
 *
 * Competitor facts are based on publicly available information as of 2026 and
 * are framed around pricing MODEL + category (which are stable) rather than
 * exact prices (which change). See `disclaimer` — surfaced on every page.
 */

export type Cell = { value: string; astra?: boolean };

export type CompareRow = {
  feature: string;
  astra: string;
  them: string;
  /** Which side this row leans toward — drives the subtle highlight only. */
  edge?: "astra" | "them" | "even";
};

export type Comparison = {
  slug: string;
  competitor: string;
  /** SEO <title> */
  title: string;
  /** meta description (~155 chars) */
  description: string;
  h1: string;
  /** 1–2 sentence intro under the H1. */
  intro: string;
  /** Honest, neutral one-paragraph description of the competitor. */
  competitorSummary: string;
  rows: CompareRow[];
  /** Genuine Astra differentiators. */
  whyAstra: string[];
  /** Honest "when the competitor is the better fit". */
  whenThem: string[];
  faqs: { q: string; a: string }[];
};

const disclaimer =
  "Comparison based on publicly available information as of 2026. Competitor features and pricing change often — please verify on their official website. Astra is not affiliated with the compared vendors.";

export const compareDisclaimer = disclaimer;

export const comparisons: Comparison[] = [
  {
    slug: "astra-vs-ninjaone",
    competitor: "NinjaOne",
    title: "Astra vs NinjaOne — AI Self-Healing vs Traditional RMM (2026)",
    description:
      "Astra vs NinjaOne compared: AI-driven autonomous self-healing with human-in-the-loop tiers vs a mature per-device RMM. See where each fits.",
    h1: "Astra vs NinjaOne",
    intro:
      "NinjaOne is a mature, per-device RMM for monitoring and managing endpoints at scale. Astra is an AI System Administrator that diagnoses and self-heals issues autonomously — with human approval where it matters. Here's an honest, side-by-side look.",
    competitorSummary:
      "NinjaOne (formerly NinjaRMM) is a well-established remote monitoring and management platform used by MSPs and internal IT teams. It's known for strong patch management, remote control, endpoint monitoring and a polished UI across Windows, macOS and Linux, priced per device.",
    rows: [
      { feature: "Category", astra: "AI System Administrator", them: "Remote Monitoring & Management (RMM)", edge: "even" },
      { feature: "Core remediation model", astra: "Agentic AI: diagnoses root cause, picks a fix, verifies it", them: "Scripts, policies & scheduled automations", edge: "astra" },
      { feature: "Autonomous self-healing", astra: "Yes — tiered, runs before a human notices", them: "Via technician-authored scripts & policies", edge: "astra" },
      { feature: "Human-in-the-loop safety tiers", astra: "Built in: automatic / approval-required / admin-only", them: "Role-based permissions & script approvals", edge: "astra" },
      { feature: "Instant secure offboarding", astra: "One-click account lock-down + forced sign-out for leavers", them: "Manual scripts or separate IAM tooling", edge: "astra" },
      { feature: "Evidence before action", astra: "Gathers telemetry + knowledge before proposing a fix", them: "Alert-and-respond, technician-led", edge: "astra" },
      { feature: "Pricing model", astra: "Per user (from $4.49/user/mo) — predictable", them: "Per device + paid add-ons (backup, EDR)", edge: "even" },
      { feature: "Patch management", astra: "Yes (Windows)", them: "Advanced, multi-OS", edge: "them" },
      { feature: "Cross-platform", astra: "Windows (today)", them: "Windows, macOS, Linux", edge: "them" },
      { feature: "Maturity & scale", astra: "Newer, AI-first", them: "Battle-tested at thousands of endpoints", edge: "them" },
      { feature: "Full audit trail on automated actions", astra: "Every action logged & attributable", them: "Activity & change logging", edge: "even" },
    ],
    whyAstra: [
      "Evidence before action — Astra collects live telemetry and searches your knowledge base before it ever proposes a fix, so automation is never blind.",
      "Human-in-the-loop by design — every remediation is classed automatic, approval-required, or admin-only, and the tier is enforced in code, not just the prompt.",
      "AI reasoning, not just scripts — Astra figures out the root cause and the right fix, runs it, then verifies the result and learns.",
      "Simple per-user pricing that stays predictable as your fleet grows — no per-device add-on creep.",
      "Secure offboarding built in — when someone leaves, lock down their account and force them out of their session in one click, so data can't walk out the door.",
    ],
    whenThem: [
      "You manage a large mixed fleet across Windows, macOS and Linux and need deep, proven patch and remote-control tooling.",
      "You want a mature RMM with a long track record at thousands of endpoints and a broad third-party integration ecosystem.",
      "Your team prefers to author its own scripts and policies rather than lean on autonomous AI remediation.",
    ],
    faqs: [
      { q: "Is Astra an RMM like NinjaOne?", a: "Astra overlaps with RMM on monitoring and remediation, but it leads with autonomous AI reasoning and built-in safety tiers rather than being a manual management console. Think of it as an AI System Administrator that acts, not just a dashboard that alerts." },
      { q: "Can Astra replace NinjaOne?", a: "For Windows-first teams that want AI-driven self-healing with approval guardrails, Astra can stand on its own. If you rely on deep multi-OS patching or a large existing NinjaOne integration stack, many teams run Astra alongside their RMM first." },
      { q: "How is Astra's pricing different?", a: "Astra is priced per user (from $4.49/user/month), while NinjaOne is priced per device with paid add-ons such as backup and EDR. Per-user pricing tends to stay more predictable as device counts grow." },
      { q: "Is autonomous remediation safe?", a: "Yes. Every action is tiered (automatic, approval-required, or admin-only), gathers evidence first, and is fully logged with an audit trail — so nothing risky runs without the right level of human approval." },
    ],
  },
  {
    slug: "astra-vs-atera",
    competitor: "Atera",
    title: "Astra vs Atera — AI System Administrator vs All-in-One RMM+PSA (2026)",
    description:
      "Astra vs Atera compared: AI-native self-healing with safety tiers vs an all-in-one per-technician RMM+PSA with an AI Copilot add-on. Where each fits.",
    h1: "Astra vs Atera",
    intro:
      "Atera is an all-in-one RMM+PSA priced per technician, with an AI Copilot add-on. Astra is an AI System Administrator where autonomous, evidence-based self-healing is the core — not a bolt-on. Here's an honest, side-by-side look.",
    competitorSummary:
      "Atera is a popular all-in-one platform that combines RMM with PSA (ticketing, billing and contracts), aimed at MSPs and IT departments. It's priced per technician rather than per device, and offers an AI Copilot and autonomous 'Robin' agent as paid add-ons.",
    rows: [
      { feature: "Category", astra: "AI System Administrator", them: "All-in-one RMM + PSA", edge: "even" },
      { feature: "AI remediation", astra: "Native & core — agentic reasoning + tiered self-healing", them: "AI Copilot / Robin agent (paid add-on)", edge: "astra" },
      { feature: "Human-in-the-loop safety tiers", astra: "Built in: automatic / approval-required / admin-only", them: "Technician-driven workflows", edge: "astra" },
      { feature: "Instant secure offboarding", astra: "One-click account lock-down + forced sign-out for leavers", them: "Manual scripts or separate IAM tooling", edge: "astra" },
      { feature: "Evidence before action", astra: "Telemetry + knowledge gathered before any fix", them: "Copilot assists the technician in real time", edge: "astra" },
      { feature: "Built-in PSA (ticketing, billing)", astra: "Focused on automation; integrates with your tools", them: "Yes — full PSA included", edge: "them" },
      { feature: "Pricing model", astra: "Per user (from $4.49/user/mo)", them: "Per technician (+ AI Copilot add-on)", edge: "even" },
      { feature: "Cross-platform", astra: "Windows (today)", them: "Windows, macOS, Linux", edge: "them" },
      { feature: "Best for", astra: "AI-first autonomous IT ops on Windows fleets", them: "MSPs wanting all-in-one RMM+PSA economics", edge: "even" },
      { feature: "Full audit trail on automated actions", astra: "Every action logged & attributable", them: "Ticket & activity history", edge: "even" },
    ],
    whyAstra: [
      "AI is the core, not an add-on — autonomous, evidence-based self-healing is built into Astra rather than sold as a separate Copilot seat.",
      "Human-in-the-loop by design — remediations are tiered automatic / approval-required / admin-only, enforced in code.",
      "Evidence before action — Astra reasons over live telemetry and your knowledge base before it acts, then verifies the outcome.",
      "Simple per-user pricing — no separate AI add-on line item to reach autonomous remediation.",
      "Secure offboarding built in — when someone leaves, lock down their account and force them out of their session in one click, so data can't walk out the door.",
    ],
    whenThem: [
      "You're an MSP that needs a built-in PSA — ticketing, billing, contracts — in the same tool as your monitoring.",
      "You prefer per-technician economics with many devices per technician, across Windows, macOS and Linux.",
      "You want a single all-in-one suite today and are comfortable with AI as an assistant to technicians rather than an autonomous operator.",
    ],
    faqs: [
      { q: "How is Astra different from Atera's AI Copilot?", a: "Atera's Copilot assists a technician while they work, as a paid add-on. In Astra, AI-driven remediation is the core of the product: it can diagnose and resolve issues autonomously within safety tiers, with a human approving anything above the automatic tier." },
      { q: "Does Astra include a PSA?", a: "No — Astra is focused on AI-driven IT operations and self-healing, and integrates with your existing tools. If you need built-in ticketing, billing and contracts, Atera's all-in-one PSA may suit you better." },
      { q: "How does pricing compare?", a: "Astra is per user (from $4.49/user/month) with autonomous remediation included. Atera is per technician, with AI Copilot billed as a separate add-on on top of the seat price." },
      { q: "Is autonomous remediation safe?", a: "Yes. Every action is tiered (automatic, approval-required, or admin-only), gathers evidence first, and is fully audited — so risky changes never run without the right human approval." },
    ],
  },
];

export function getComparison(slug: string): Comparison | undefined {
  return comparisons.find((c) => c.slug === slug);
}
