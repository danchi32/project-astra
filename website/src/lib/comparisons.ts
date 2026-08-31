/**
 * Data for the /compare/[slug] landing pages (ASTRA vs <competitor>).
 *
 * Positioning is deliberately HONEST and balanced: some rows favour ASTRA, some
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
  /** Genuine ASTRA differentiators. */
  whyAstra: string[];
  /** Honest "when the competitor is the better fit". */
  whenThem: string[];
  faqs: { q: string; a: string }[];
  sourceReviewed?: string;
  sources?: { label: string; href: string }[];
};

const disclaimer =
  "Comparison based on publicly available information as of 2026. Competitor features and pricing change often — please verify on their official website. ASTRA is not affiliated with the compared vendors.";

export const compareDisclaimer = disclaimer;

export const comparisons: Comparison[] = [
  {
    slug: "astra-vs-microsoft-intune",
    competitor: "Microsoft Intune",
    title: "ASTRA vs Microsoft Intune — AI IT Operations vs UEM (2026)",
    description:
      "Compare ASTRA and Microsoft Intune for Windows operations: evidence-first remediation and approval tiers vs mature cross-platform device management.",
    h1: "ASTRA vs Microsoft Intune",
    intro:
      "Microsoft Intune is a mature, cross-platform unified endpoint management service in the Microsoft ecosystem. ASTRA is a Windows-focused AI System Administrator built around evidence-first diagnosis, governed remediation and verification. The right choice depends on whether your priority is broad policy management or an AI operations loop.",
    competitorSummary:
      "Microsoft Intune manages and protects Windows, macOS, iOS and Android endpoints from a cloud console. It provides device and app management, compliance policy, remote actions and endpoint analytics, and is included with several Microsoft 365 and Enterprise Mobility + Security subscriptions.",
    rows: [
      { feature: "Category", astra: "AI System Administrator", them: "Unified endpoint management (UEM)", edge: "even" },
      { feature: "Primary workflow", astra: "Evidence → diagnosis → authorization → remediation → verification", them: "Enrollment → policy → compliance → remote administration", edge: "even" },
      { feature: "AI-driven remediation", astra: "Core product workflow with code-enforced action tiers", them: "Analytics, policies and remediations within the Microsoft management stack", edge: "astra" },
      { feature: "Human approval boundaries", astra: "Automatic / approval-required / admin-only tiers", them: "Role-based access, assignments and policy controls", edge: "even" },
      { feature: "Device platforms", astra: "Windows 10 and 11 (64-bit)", them: "Windows, macOS, iOS and Android", edge: "them" },
      { feature: "Mobile application management", astra: "Not currently offered", them: "Built-in app protection and management", edge: "them" },
      { feature: "Endpoint analytics", astra: "Live fleet telemetry and remediation context", them: "Device performance, startup, app reliability and related reports", edge: "even" },
      { feature: "Pricing model", astra: "Per device, published plans", them: "Per user; also included in several Microsoft subscriptions", edge: "even" },
      { feature: "Best fit", astra: "Windows teams prioritizing controlled AI diagnosis and verified fixes", them: "Organizations standardized on Microsoft and needing broad UEM", edge: "even" },
    ],
    whyAstra: [
      "Evidence before action — ASTRA combines the request, enterprise knowledge and live endpoint telemetry before selecting a remediation.",
      "Explicit action governance — automatic, approval-required and admin-only tiers are enforced in backend code rather than left to an AI prompt.",
      "Post-action verification — the workflow checks and records the result instead of treating command delivery as resolution.",
      "Focused evaluation — Windows-first teams can test the reasoning-to-verification loop on a limited device group.",
    ],
    whenThem: [
      "Your organization needs mature management across Windows, macOS, iOS and Android from one Microsoft-aligned platform.",
      "Device compliance, mobile application management and Microsoft 365 identity integration are primary requirements.",
      "Intune is already included in your licensing and your team is invested in Microsoft administration workflows.",
    ],
    faqs: [
      { q: "Is ASTRA a replacement for Microsoft Intune?", a: "Not in every environment. Intune is broader UEM for device, app and compliance management across several operating systems. ASTRA is focused on Windows evidence, diagnosis and controlled remediation. A pilot should assess whether ASTRA complements or replaces specific current workflows." },
      { q: "Which product supports more operating systems?", a: "Microsoft Intune supports Windows, macOS, iOS and Android management. The ASTRA endpoint agent currently supports 64-bit Windows 10 and Windows 11." },
      { q: "How do their pricing models differ?", a: "ASTRA uses per-device plans. Microsoft lists Intune Plan 1 per user and also includes it in several Microsoft 365 and Enterprise Mobility + Security subscriptions. Verify current regional pricing and your existing license entitlements before comparing cost." },
      { q: "What is ASTRA's main difference?", a: "ASTRA is built around an evidence-to-verification loop: gather live context, diagnose, apply a code-enforced approval tier, execute an allowlisted action and verify the result." },
    ],
    sourceReviewed: "30 August 2026",
    sources: [
      { label: "Microsoft Intune plans and pricing", href: "https://www.microsoft.com/en-us/security/business/microsoft-intune-pricing" },
      { label: "Microsoft Intune product features", href: "https://www.microsoft.com/en-us/security/business/endpoint-management/microsoft-intune" },
      { label: "Microsoft Learn: Endpoint analytics overview", href: "https://learn.microsoft.com/en-us/intune/analytics/" },
    ],
  },
  {
    slug: "astra-vs-manageengine-endpoint-central",
    competitor: "ManageEngine Endpoint Central",
    title: "ASTRA vs ManageEngine Endpoint Central (2026)",
    description:
      "Compare ASTRA and ManageEngine Endpoint Central: governed AI remediation for Windows vs broad endpoint management, patching and security.",
    h1: "ASTRA vs ManageEngine Endpoint Central",
    intro:
      "ManageEngine Endpoint Central is a broad endpoint management and security platform with deep patching, configuration and multi-OS capabilities. ASTRA is a Windows-focused AI System Administrator designed to reason from live evidence, enforce action boundaries and verify remediation.",
    competitorSummary:
      "ManageEngine Endpoint Central provides endpoint management and security across desktop and mobile platforms. Its official materials cover patching, software deployment, asset management, remote troubleshooting, configurations, reporting, mobile device management and multiple deployment editions.",
    rows: [
      { feature: "Category", astra: "AI System Administrator", them: "Unified endpoint management and security", edge: "even" },
      { feature: "Core workflow", astra: "AI reasoning with evidence, governed action and verification", them: "Policies, configurations, automation and technician tools", edge: "even" },
      { feature: "Approval model", astra: "Three code-enforced remediation tiers", them: "Roles, configurations, deployment controls and approvals", edge: "even" },
      { feature: "Device platforms", astra: "Windows 10 and 11 (64-bit)", them: "Broad desktop and mobile OS coverage", edge: "them" },
      { feature: "Patch management", astra: "Windows update visibility and controlled workflows", them: "Deep OS and third-party patch management", edge: "them" },
      { feature: "OS deployment and imaging", astra: "Not currently offered", them: "Available within the platform", edge: "them" },
      { feature: "Evidence before remediation", astra: "Required reasoning step using telemetry and knowledge", them: "Monitoring, reports, policies and administrator-led tooling", edge: "astra" },
      { feature: "Post-action verification", astra: "Part of the cognitive remediation loop", them: "Activity, status and reporting capabilities", edge: "astra" },
      { feature: "Deployment and pricing", astra: "Cloud SaaS priced per device", them: "Cloud and on-premises editions with endpoint/technician bands", edge: "even" },
      { feature: "Best fit", astra: "Lean Windows teams seeking controlled AI operations", them: "Teams needing broad, mature endpoint administration depth", edge: "even" },
    ],
    whyAstra: [
      "AI operations is the product core — ASTRA reasons over live evidence and approved knowledge before choosing a permitted fix.",
      "Authorization boundaries are explicit — the model cannot lower an approval-required or admin-only action into an automatic tier.",
      "Verification closes the loop — ASTRA records whether the attempted remediation produced the expected endpoint state.",
      "A focused Windows workflow can reduce evaluation complexity for lean teams that do not need a broad multi-platform administration suite.",
    ],
    whenThem: [
      "You need established patching, software distribution, OS imaging and configuration capabilities across multiple operating systems.",
      "Your environment requires on-premises deployment options or broad mobile device management.",
      "You prefer a comprehensive endpoint administration suite and technician-led automation over a focused AI reasoning loop.",
    ],
    faqs: [
      { q: "Is ASTRA a full replacement for Endpoint Central?", a: "Not for every use case. Endpoint Central offers broader endpoint administration, multi-OS management, patching and deployment capabilities. ASTRA is best evaluated for its Windows evidence-to-verification workflow and controlled AI remediation." },
      { q: "Which platform is broader?", a: "ManageEngine Endpoint Central is broader across operating systems and endpoint management functions. ASTRA is intentionally focused on Windows IT operations and governed remediation." },
      { q: "How should we compare pricing?", a: "ASTRA publishes per-device SaaS plans. Endpoint Central offers multiple editions, deployment models and endpoint bands. Use your device, server, technician and add-on requirements with the current official calculators rather than comparing a single headline price." },
      { q: "Can ASTRA be evaluated alongside Endpoint Central?", a: "Yes. A limited-device pilot can test ASTRA's diagnosis, approval and verification workflow while coexistence requirements are reviewed against your current Endpoint Central configuration." },
    ],
    sourceReviewed: "30 August 2026",
    sources: [
      { label: "Endpoint Central features", href: "https://www.manageengine.com/products/desktop-central/features.html" },
      { label: "Endpoint Central OS comparison matrix", href: "https://www.manageengine.com/products/desktop-central/os-comparison-matrix.html" },
      { label: "Endpoint Central pricing", href: "https://www.manageengine.com/products/desktop-central/pricing.html" },
    ],
  },
  {
    slug: "astra-vs-ninjaone",
    competitor: "NinjaOne",
    title: "ASTRA vs NinjaOne — AI Self-Healing vs Traditional RMM (2026)",
    description:
      "ASTRA vs NinjaOne compared: AI-driven autonomous self-healing with human-in-the-loop tiers vs a mature per-device RMM. See where each fits.",
    h1: "ASTRA vs NinjaOne",
    intro:
      "NinjaOne is a mature, per-device RMM for monitoring and managing endpoints at scale. ASTRA is an AI System Administrator that diagnoses and self-heals issues autonomously — with human approval where it matters. Here's an honest, side-by-side look.",
    competitorSummary:
      "NinjaOne (formerly NinjaRMM) is a well-established remote monitoring and management platform used by MSPs and internal IT teams. It's known for strong patch management, remote control, endpoint monitoring and a polished UI across Windows, macOS and Linux, priced per device.",
    rows: [
      { feature: "Category", astra: "AI System Administrator", them: "Remote Monitoring & Management (RMM)", edge: "even" },
      { feature: "Core remediation model", astra: "Agentic AI: diagnoses root cause, picks a fix, verifies it", them: "Scripts, policies & scheduled automations", edge: "astra" },
      { feature: "Autonomous self-healing", astra: "Yes — tiered, runs before a human notices", them: "Via technician-authored scripts & policies", edge: "astra" },
      { feature: "Human-in-the-loop safety tiers", astra: "Built in: automatic / approval-required / admin-only", them: "Role-based permissions & script approvals", edge: "astra" },
      { feature: "Instant secure offboarding", astra: "One-click account lock-down + forced sign-out for leavers", them: "Manual scripts or separate IAM tooling", edge: "astra" },
      { feature: "Evidence before action", astra: "Gathers telemetry + knowledge before proposing a fix", them: "Alert-and-respond, technician-led", edge: "astra" },
      { feature: "Pricing model", astra: "Per device (from $4.49/device/mo) — all-in tiers", them: "Per device + paid add-ons (backup, EDR)", edge: "even" },
      { feature: "Patch management", astra: "Yes (Windows)", them: "Advanced, multi-OS", edge: "them" },
      { feature: "Cross-platform", astra: "Windows (today)", them: "Windows, macOS, Linux", edge: "them" },
      { feature: "Maturity & scale", astra: "Newer, AI-first", them: "Battle-tested at thousands of endpoints", edge: "them" },
      { feature: "Full audit trail on automated actions", astra: "Every action logged & attributable", them: "Activity & change logging", edge: "even" },
    ],
    whyAstra: [
      "Evidence before action — ASTRA collects live telemetry and searches your knowledge base before it ever proposes a fix, so automation is never blind.",
      "Human-in-the-loop by design — every remediation is classed automatic, approval-required, or admin-only, and the tier is enforced in code, not just the prompt.",
      "AI reasoning, not just scripts — ASTRA figures out the root cause and the right fix, runs it, then verifies the result and learns.",
      "Simple per-device pricing where each tier is all-inclusive — no add-on creep for backup or EDR.",
      "Secure offboarding built in — when someone leaves, lock down their account and force them out of their session in one click, so data can't walk out the door.",
    ],
    whenThem: [
      "You manage a large mixed fleet across Windows, macOS and Linux and need deep, proven patch and remote-control tooling.",
      "You want a mature RMM with a long track record at thousands of endpoints and a broad third-party integration ecosystem.",
      "Your team prefers to author its own scripts and policies rather than lean on autonomous AI remediation.",
    ],
    faqs: [
      { q: "Is ASTRA an RMM like NinjaOne?", a: "ASTRA overlaps with RMM on monitoring and remediation, but it leads with autonomous AI reasoning and built-in safety tiers rather than being a manual management console. Think of it as an AI System Administrator that acts, not just a dashboard that alerts." },
      { q: "Can ASTRA replace NinjaOne?", a: "For Windows-first teams that want AI-driven self-healing with approval guardrails, ASTRA can stand on its own. If you rely on deep multi-OS patching or a large existing NinjaOne integration stack, many teams run ASTRA alongside their RMM first." },
      { q: "How is ASTRA's pricing different?", a: "Both are priced per device, but each ASTRA tier is all-inclusive — AI self-healing, offboarding and compliance are part of the plan rather than paid add-ons like backup and EDR. ASTRA starts at $4.49/device/month." },
      { q: "Is autonomous remediation safe?", a: "Yes. Every action is tiered (automatic, approval-required, or admin-only), gathers evidence first, and is fully logged with an audit trail — so nothing risky runs without the right level of human approval." },
    ],
  },
  {
    slug: "astra-vs-atera",
    competitor: "Atera",
    title: "ASTRA vs Atera — AI System Administrator vs All-in-One RMM+PSA (2026)",
    description:
      "ASTRA vs Atera compared: AI-native self-healing with safety tiers vs an all-in-one per-technician RMM+PSA with an AI Copilot add-on. Where each fits.",
    h1: "ASTRA vs Atera",
    intro:
      "Atera is an all-in-one RMM+PSA priced per technician, with an AI Copilot add-on. ASTRA is an AI System Administrator where autonomous, evidence-based self-healing is the core — not a bolt-on. Here's an honest, side-by-side look.",
    competitorSummary:
      "Atera is a popular all-in-one platform that combines RMM with PSA (ticketing, billing and contracts), aimed at MSPs and IT departments. It's priced per technician rather than per device, and offers an AI Copilot and autonomous 'Robin' agent as paid add-ons.",
    rows: [
      { feature: "Category", astra: "AI System Administrator", them: "All-in-one RMM + PSA", edge: "even" },
      { feature: "AI remediation", astra: "Native & core — agentic reasoning + tiered self-healing", them: "AI Copilot / Robin agent (paid add-on)", edge: "astra" },
      { feature: "Human-in-the-loop safety tiers", astra: "Built in: automatic / approval-required / admin-only", them: "Technician-driven workflows", edge: "astra" },
      { feature: "Instant secure offboarding", astra: "One-click account lock-down + forced sign-out for leavers", them: "Manual scripts or separate IAM tooling", edge: "astra" },
      { feature: "Evidence before action", astra: "Telemetry + knowledge gathered before any fix", them: "Copilot assists the technician in real time", edge: "astra" },
      { feature: "Built-in PSA (ticketing, billing)", astra: "Focused on automation; integrates with your tools", them: "Yes — full PSA included", edge: "them" },
      { feature: "Pricing model", astra: "Per device (from $4.49/device/mo)", them: "Per technician (+ AI Copilot add-on)", edge: "even" },
      { feature: "Cross-platform", astra: "Windows (today)", them: "Windows, macOS, Linux", edge: "them" },
      { feature: "Best for", astra: "AI-first autonomous IT ops on Windows fleets", them: "MSPs wanting all-in-one RMM+PSA economics", edge: "even" },
      { feature: "Full audit trail on automated actions", astra: "Every action logged & attributable", them: "Ticket & activity history", edge: "even" },
    ],
    whyAstra: [
      "AI is the core, not an add-on — autonomous, evidence-based self-healing is built into ASTRA rather than sold as a separate Copilot seat.",
      "Human-in-the-loop by design — remediations are tiered automatic / approval-required / admin-only, enforced in code.",
      "Evidence before action — ASTRA reasons over live telemetry and your knowledge base before it acts, then verifies the outcome.",
      "Simple per-device pricing — no separate AI add-on line item to reach autonomous remediation.",
      "Secure offboarding built in — when someone leaves, lock down their account and force them out of their session in one click, so data can't walk out the door.",
    ],
    whenThem: [
      "You're an MSP that needs a built-in PSA — ticketing, billing, contracts — in the same tool as your monitoring.",
      "You prefer per-technician economics with many devices per technician, across Windows, macOS and Linux.",
      "You want a single all-in-one suite today and are comfortable with AI as an assistant to technicians rather than an autonomous operator.",
    ],
    faqs: [
      { q: "How is ASTRA different from Atera's AI Copilot?", a: "Atera's Copilot assists a technician while they work, as a paid add-on. In ASTRA, AI-driven remediation is the core of the product: it can diagnose and resolve issues autonomously within safety tiers, with a human approving anything above the automatic tier." },
      { q: "Does ASTRA include a PSA?", a: "No — ASTRA is focused on AI-driven IT operations and self-healing, and integrates with your existing tools. If you need built-in ticketing, billing and contracts, Atera's all-in-one PSA may suit you better." },
      { q: "How does pricing compare?", a: "ASTRA is priced per device (from $4.49/device/month), with autonomous remediation included from the Professional tier. Atera is priced per technician, with AI Copilot billed as a separate add-on on top of the seat price." },
      { q: "Is autonomous remediation safe?", a: "Yes. Every action is tiered (automatic, approval-required, or admin-only), gathers evidence first, and is fully audited — so risky changes never run without the right human approval." },
    ],
  },
];

export function getComparison(slug: string): Comparison | undefined {
  return comparisons.find((c) => c.slug === slug);
}
