"use client";

import {
  Sparkles,
  ArrowRight,
  Boxes,
  Activity,
  Wrench,
  BrainCircuit,
  ShieldCheck,
  Bell,
  FileBarChart,
  Network,
  Lock,
  KeyRound,
  ScrollText,
  BadgeCheck,
  Search,
  MessageSquare,
  Gauge,
  Cpu,
  RefreshCcw,
  DownloadCloud,
  UserX,
  LogOut,
  ClipboardCheck,
  Ban,
  Ticket,
  GraduationCap,
  MailCheck,
} from "lucide-react";
import {
  Container,
  Section,
  Reveal,
  Badge,
  SectionHeading,
  Button,
} from "@/components/ui";
import { TiltCard, Magnetic } from "@/components/enhance";
import { Hero3D } from "@/components/three/Hero3D";
import { AnimatedBackground } from "@/components/AnimatedBackground";
import {
  DashboardMockup,
  InventoryPanel,
  TelemetryGauges,
  AiConsole,
  ApprovalTiers,
  SelfHealingFlow,
  PatchPushPanel,
} from "@/components/visuals";
import { useContent, Rich } from "@/lib/content";
import { site, bookDemo } from "@/lib/site";

const featureIcons = [
  Boxes, Activity, BrainCircuit, Wrench, DownloadCloud,
  UserX, MessageSquare, ShieldCheck, FileBarChart, Bell, ScrollText,
  ClipboardCheck, Ban, Network, Ticket, GraduationCap, MailCheck,
];
const featureDefaults = [
  { title: "Asset Inventory", desc: "A live, auto-discovered registry of every device, spec, app and license across your fleet." },
  { title: "Live Telemetry", desc: "CPU, RAM, disk, event logs, apps, services and Windows updates streamed in real time." },
  { title: "AI Cognitive Engine", desc: "An agentic reasoning loop that recognizes intent, searches knowledge and scores confidence." },
  { title: "Self-Healing", desc: "Allowlisted, tiered remediations that fix issues automatically — or with approval." },
  { title: "Patch Management", desc: "Push Windows Updates to any device — or the whole fleet — from the admin panel and watch rollout live." },
  { title: "Secure Offboarding", desc: "When someone leaves, lock down their account and force them out of their session in one click — before data can walk out." },
  { title: "Conversational AI", desc: "Users describe problems in plain language; ASTRA investigates and resolves." },
  { title: "Approval Tiers", desc: "Automatic, approval-required and admin-only — enforced in code, not just prompts." },
  { title: "Reporting", desc: "Fleet health, resolution and compliance reports ready for stakeholders." },
  { title: "Notifications", desc: "Proactive alerts the moment something needs a human decision." },
  { title: "Full Audit Trail", desc: "Every mutation and agent command is logged, attributable and reviewable." },
  { title: "Compliance & Security Posture", desc: "A live compliance dashboard scores your fleet's security posture and flags the devices that fall short." },
  { title: "Restricted Software Detection", desc: "Spot unapproved or risky applications across every device, so shadow IT surfaces before it becomes an incident." },
  { title: "Fleet Correlation & Mass Remediation", desc: "ASTRA links the same fault across many devices, then fixes the whole affected group in one click instead of one by one." },
  { title: "Helpdesk Integration", desc: "Connect Freshservice and let ASTRA raise a ticket for what it can't fix itself — with the device's evidence attached, and only after the user agrees." },
  { title: "Self-Learning Knowledge Base", desc: "Every confirmed fix teaches the knowledge base. ASTRA publishes what repeatedly works, drops advice whose success rate falls, and keeps the words users actually type." },
  { title: "Asset Assignment & Acknowledgement", desc: "Hand a laptop to an employee and ASTRA emails them to confirm receipt — sent from your own verified domain, with the signed acknowledgement kept on the asset record." },
];

const workflowIcons = [Search, BrainCircuit, Activity, Gauge, Wrench, BadgeCheck];
const workflowDefaults = [
  { label: "Intent", desc: "Understand the request" },
  { label: "Knowledge", desc: "Search enterprise KB" },
  { label: "Telemetry", desc: "Collect live evidence" },
  { label: "Confidence", desc: "Score the diagnosis" },
  { label: "Self-heal", desc: "Act within tier" },
  { label: "Verify", desc: "Confirm & learn" },
];

const securityIcons = [KeyRound, Lock, BadgeCheck, ScrollText];
const securityDefaults = [
  { title: "JWT + RBAC", desc: "Short-lived tokens and role-based access on every endpoint." },
  { title: "Encrypted everywhere", desc: "Encryption in transit and at rest, HTTPS-only." },
  { title: "Per-device credentials", desc: "Each agent enrolls with an organization key, then authenticates with its own token." },
  { title: "Audit logs", desc: "Immutable records for all mutations and commands." },
];

const telemetryItemIcons = [Gauge, Network, RefreshCcw, Activity];
const telemetryItemDefaults = [
  "60-second heartbeat",
  "Offline-safe queue",
  "Update tracking",
  "Event-log insight",
];

export function AstraContent() {
  const { c, list } = useContent();
  const workflow = list("astra.workflow", workflowDefaults);
  const features = list("astra.features", featureDefaults);
  const security = list("astra.security", securityDefaults);
  const inventoryBullets = list<string>("astra.inventory.bullets", [
    "Auto-discovery on enrollment",
    "Hardware, software & license tracking",
    "Health status at a glance",
    "Search and filter across the fleet",
  ]);
  const telemetryItems = list<string>("astra.telemetry.items", telemetryItemDefaults);
  const patchBullets = list<string>("astra.patch.bullets", [
    "One-click push to a device or whole fleet",
    "Live rollout status for every endpoint",
    "Driven from Telemetry → Updates in the portal",
    "Every push captured in the audit log",
  ]);
  const offboardingBullets = list<string>("astra.offboarding.bullets", [
    "Instantly disable a departing employee's local account",
    "Force sign-out — ends their active Windows session, not just next login",
    "Matches the exact user by security ID (SID), never the wrong account",
    "Admin-only tier with a full audit trail on every lock-down",
  ]);

  return (
    <>
      {/* ------------------------------------------------------------ HERO */}
      {/* Pulled up by the header's height so the aurora starts at the very top
          of the page and washes behind the (transparent) header. The top
          padding absorbs that shift, keeping content where it was. */}
      <section className="aurora grain relative -mt-16 overflow-hidden pt-28 pb-16 sm:pt-36">
        <AnimatedBackground dense />
        <Container>
          <div className="grid items-center gap-10 lg:grid-cols-2">
            <div>
              <Reveal>
                <Badge>
                  <Sparkles className="h-3.5 w-3.5 text-brand-500" />{" "}
                  {c("astra.badge", "Meet ASTRA")}
                </Badge>
              </Reveal>
              <Reveal delay={0.05}>
                <h1 className="mt-5 text-4xl font-extrabold leading-[1.08] tracking-tight sm:text-6xl">
                  <Rich text={c("astra.title", "Your [[AI System Administrator]]")} />
                </h1>
              </Reveal>
              <Reveal delay={0.1}>
                <p className="mt-6 max-w-xl text-lg leading-relaxed text-secondary-token">
                  {c(
                    "astra.subtitle",
                    "ASTRA watches every device, understands issues in plain English, gathers evidence, and heals problems automatically — with human-in-the-loop control at every tier that matters.",
                  )}
                </p>
              </Reveal>
              <Reveal delay={0.15}>
                <div className="mt-8 flex flex-wrap gap-3">
                  <Magnetic>
                    <Button href={site.appUrl} external>
                      {c("astra.cta1", "Launch ASTRA")}{" "}
                      <ArrowRight className="h-4 w-4" />
                    </Button>
                  </Magnetic>
                  <Button href="/pricing" variant="secondary">
                    {c("astra.cta2", "View pricing")}
                  </Button>
                </div>
              </Reveal>
            </div>

            <Reveal delay={0.15} className="flex justify-center">
              <Hero3D />
            </Reveal>
          </div>

          <Reveal delay={0.2}>
            <div className="mx-auto mt-16 max-w-4xl animate-float">
              <DashboardMockup />
            </div>
          </Reveal>
        </Container>
      </section>

      {/* ---------------------------------------------------- HOW IT WORKS */}
      <Section>
        <Container>
          <Reveal>
            <SectionHeading
              eyebrow={c("astra.loopHead.eyebrow", "The ASTRA loop")}
              title={c("astra.loopHead.title", "An agentic workflow, not a black box")}
              subtitle={c(
                "astra.loopHead.subtitle",
                "Each step is a tool the model calls — evidence before action, verification after.",
              )}
            />
          </Reveal>
          <div className="mt-14 grid gap-4 sm:grid-cols-3 lg:grid-cols-6">
            {workflow.map((w, i) => {
              const Icon = workflowIcons[i % workflowIcons.length];
              return (
                <Reveal key={w.label} delay={i * 0.08}>
                  <div className="relative h-full rounded-2xl border border-token bg-surface p-5 text-center">
                    <div className="mx-auto grid h-11 w-11 place-items-center rounded-xl bg-brand-500/10 text-brand-500">
                      <Icon className="h-5 w-5" />
                    </div>
                    <div className="mt-3 text-sm font-bold">{w.label}</div>
                    <div className="mt-1 text-xs text-muted-token">{w.desc}</div>
                    <span className="absolute -top-2 left-3 text-xs font-bold text-brand-500/40">
                      {String(i + 1).padStart(2, "0")}
                    </span>
                  </div>
                </Reveal>
              );
            })}
          </div>
        </Container>
      </Section>

      {/* ------------------------------------------------------- FEATURES */}
      <Section className="bg-surface">
        <Container>
          <Reveal>
            <SectionHeading
              eyebrow={c("astra.capsHead.eyebrow", "Capabilities")}
              title={c("astra.capsHead.title", "Everything ASTRA does out of the box")}
              subtitle={c(
                "astra.capsHead.subtitle",
                "A complete AI operations platform for your Windows fleet.",
              )}
            />
          </Reveal>
          <div className="mt-14 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {features.map((f, i) => {
              const Icon = featureIcons[i % featureIcons.length];
              return (
                <Reveal key={f.title} delay={(i % 3) * 0.08}>
                  <TiltCard className="h-full">
                    <div className="ring-conic h-full rounded-2xl border border-token bg-app p-6 transition-all hover:border-brand-500/40 hover:shadow-lg">
                      <div className="grid h-11 w-11 place-items-center rounded-xl bg-brand-500/10 text-brand-500">
                        <Icon className="h-5 w-5" />
                      </div>
                      <h3 className="mt-4 text-base font-bold">{f.title}</h3>
                      <p className="mt-1.5 text-sm leading-relaxed text-secondary-token">
                        {f.desc}
                      </p>
                    </div>
                  </TiltCard>
                </Reveal>
              );
            })}
          </div>
        </Container>
      </Section>

      {/* ------------------------------------------------ DEEP DIVE: INVENTORY */}
      <Section>
        <Container>
          <div className="grid items-center gap-12 lg:grid-cols-2">
            <Reveal>
              <div>
                <Badge>
                  <Boxes className="h-3.5 w-3.5 text-brand-500" />{" "}
                  {c("astra.inventory.badge", "Inventory")}
                </Badge>
                <h2 className="mt-4 text-3xl font-bold tracking-tight sm:text-4xl">
                  {c("astra.inventory.title", "Know every device, automatically")}
                </h2>
                <p className="mt-4 text-secondary-token">
                  {c(
                    "astra.inventory.desc",
                    "The moment an agent enrolls, ASTRA builds a live inventory — hardware specs, installed apps, services, licenses and health. No spreadsheets, no manual audits, always current.",
                  )}
                </p>
                <ul className="mt-5 space-y-2.5">
                  {inventoryBullets.map((t) => (
                    <li key={t} className="flex items-center gap-2.5 text-sm text-secondary-token">
                      <BadgeCheck className="h-4 w-4 text-emerald-500" /> {t}
                    </li>
                  ))}
                </ul>
              </div>
            </Reveal>
            <Reveal delay={0.1}>
              <InventoryPanel />
            </Reveal>
          </div>
        </Container>
      </Section>

      {/* ------------------------------------------------ DEEP DIVE: TELEMETRY */}
      <Section className="bg-surface">
        <Container>
          <div className="grid items-center gap-12 lg:grid-cols-2">
            <Reveal className="order-2 lg:order-1">
              <TelemetryGauges />
            </Reveal>
            <Reveal delay={0.1} className="order-1 lg:order-2">
              <div>
                <Badge>
                  <Cpu className="h-3.5 w-3.5 text-brand-500" />{" "}
                  {c("astra.telemetry.badge", "Telemetry")}
                </Badge>
                <h2 className="mt-4 text-3xl font-bold tracking-tight sm:text-4xl">
                  {c("astra.telemetry.title", "Real-time evidence from every endpoint")}
                </h2>
                <p className="mt-4 text-secondary-token">
                  {c(
                    "astra.telemetry.desc",
                    "A lightweight Windows agent streams CPU, memory, disk, event logs, running apps, services and Windows Update status back to the platform — the raw evidence ASTRA reasons over.",
                  )}
                </p>
                <div className="mt-6 grid grid-cols-2 gap-3">
                  {telemetryItems.map((t, i) => {
                    const Icon = telemetryItemIcons[i % telemetryItemIcons.length];
                    return (
                      <div
                        key={t}
                        className="flex items-center gap-2.5 rounded-xl border border-token bg-app p-3 text-sm"
                      >
                        <Icon className="h-4 w-4 text-brand-500" /> {t}
                      </div>
                    );
                  })}
                </div>
              </div>
            </Reveal>
          </div>
        </Container>
      </Section>

      {/* ------------------------------------------ DEEP DIVE: SELF-HEALING */}
      <Section>
        <Container>
          <Reveal>
            <SectionHeading
              eyebrow={c("astra.healingHead.eyebrow", "Self-healing")}
              title={c("astra.healingHead.title", "Fixes that respect human control")}
              subtitle={c(
                "astra.healingHead.subtitle",
                "ASTRA never runs a higher-tier action without the right approval — enforced in the backend, never only in the prompt.",
              )}
            />
          </Reveal>
          <Reveal delay={0.1}>
            <div className="mt-12">
              <SelfHealingFlow />
            </div>
          </Reveal>
          <Reveal delay={0.15}>
            <div className="mt-8">
              <ApprovalTiers />
            </div>
          </Reveal>
        </Container>
      </Section>

      {/* ------------------------------------------ DEEP DIVE: PATCH MGMT */}
      <Section className="bg-surface">
        <Container>
          <div className="grid items-center gap-12 lg:grid-cols-2">
            <Reveal>
              <div>
                <Badge>
                  <DownloadCloud className="h-3.5 w-3.5 text-brand-500" />{" "}
                  {c("astra.patch.badge", "Patch Management")}
                </Badge>
                <h2 className="mt-4 text-3xl font-bold tracking-tight sm:text-4xl">
                  <Rich
                    text={c(
                      "astra.patch.title",
                      "Push Windows Updates [[from the admin panel]]",
                    )}
                  />
                </h2>
                <p className="mt-4 text-secondary-token">
                  {c(
                    "astra.patch.desc",
                    "Spot a missing security patch in telemetry, then deploy it to a single device or the entire fleet in one click. ASTRA orchestrates the rollout and streams live progress — Pending, Downloading, Installing, Installed — so you always know exactly where every endpoint stands.",
                  )}
                </p>
                <ul className="mt-5 space-y-2.5">
                  {patchBullets.map((t) => (
                    <li
                      key={t}
                      className="flex items-center gap-2.5 text-sm text-secondary-token"
                    >
                      <BadgeCheck className="h-4 w-4 text-emerald-500" /> {t}
                    </li>
                  ))}
                </ul>
              </div>
            </Reveal>
            <Reveal delay={0.1}>
              <PatchPushPanel />
            </Reveal>
          </div>
        </Container>
      </Section>

      {/* ------------------------------------------ DEEP DIVE: OFFBOARDING */}
      <Section>
        <Container>
          <div className="grid items-center gap-12 lg:grid-cols-2">
            <Reveal>
              <div>
                <Badge>
                  <UserX className="h-3.5 w-3.5 text-brand-500" />{" "}
                  {c("astra.offboarding.badge", "Secure Offboarding")}
                </Badge>
                <h2 className="mt-4 text-3xl font-bold tracking-tight sm:text-4xl">
                  <Rich
                    text={c(
                      "astra.offboarding.title",
                      "Stop data walking out [[the door]]",
                    )}
                  />
                </h2>
                <p className="mt-4 text-secondary-token">
                  {c(
                    "astra.offboarding.desc",
                    "Offboarding is the riskiest moment for your data — a leaver with an open session can copy files long after HR says goodbye. With ASTRA, lock down their account and force them out of their active Windows session in one click. Instant, precise and fully audited.",
                  )}
                </p>
                <ul className="mt-5 space-y-2.5">
                  {offboardingBullets.map((t) => (
                    <li
                      key={t}
                      className="flex items-center gap-2.5 text-sm text-secondary-token"
                    >
                      <BadgeCheck className="h-4 w-4 text-emerald-500" /> {t}
                    </li>
                  ))}
                </ul>
              </div>
            </Reveal>

            {/* Lock-down sequence visual */}
            <Reveal delay={0.1}>
              <div className="rounded-2xl border border-token bg-surface p-6">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-semibold">Lock-down sequence</span>
                  <span className="rounded-full bg-rose-500/10 px-2.5 py-1 text-xs font-semibold text-rose-500">
                    Employee offboarded
                  </span>
                </div>
                <ol className="mt-5 space-y-3">
                  {[
                    { icon: Lock, label: "Disable local account", tag: "instant" },
                    { icon: LogOut, label: "Force sign-out of active session", tag: "SID-matched" },
                    { icon: ShieldCheck, label: "Block re-login", tag: "enforced" },
                    { icon: ScrollText, label: "Action written to audit trail", tag: "logged" },
                  ].map((step, i) => {
                    const Icon = step.icon;
                    return (
                      <li
                        key={step.label}
                        className="flex items-center gap-3 rounded-xl border border-token bg-app p-3"
                      >
                        <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-brand-500/10 text-brand-500">
                          <Icon className="h-4 w-4" />
                        </span>
                        <span className="flex-1 text-sm font-medium">
                          {step.label}
                        </span>
                        <span className="text-[11px] font-semibold uppercase tracking-wide text-muted-token">
                          {step.tag}
                        </span>
                        <span className="ml-1 hidden text-xs font-bold text-brand-500/40 sm:inline">
                          {String(i + 1).padStart(2, "0")}
                        </span>
                      </li>
                    );
                  })}
                </ol>
              </div>
            </Reveal>
          </div>
        </Container>
      </Section>

      {/* ------------------------------------------ DEEP DIVE: ASSISTANT */}
      <Section>
        <Container>
          <div className="grid items-center gap-12 lg:grid-cols-2">
            <Reveal>
              <div>
                <Badge>
                  <MessageSquare className="h-3.5 w-3.5 text-brand-500" />{" "}
                  {c("astra.assistant.badge", "Conversational AI")}
                </Badge>
                <h2 className="mt-4 text-3xl font-bold tracking-tight sm:text-4xl">
                  {c("astra.assistant.title", "Support that speaks human")}
                </h2>
                <p className="mt-4 text-secondary-token">
                  {c(
                    "astra.assistant.desc",
                    "Employees just describe the problem. ASTRA recognizes intent, pulls the relevant knowledge, collects telemetry, and walks through the fix — escalating to a person only when a decision truly needs one.",
                  )}
                </p>
                <div className="mt-6">
                  <Button href={site.appUrl} external>
                    {c("astra.assistant.cta", "Try the assistant")}{" "}
                    <ArrowRight className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            </Reveal>
            <Reveal delay={0.1}>
              <AiConsole />
            </Reveal>
          </div>
        </Container>
      </Section>

      {/* ------------------------------------------------------- SECURITY */}
      <Section>
        <Container>
          <Reveal>
            <SectionHeading
              eyebrow={c("astra.securityHead.eyebrow", "Security")}
              title={c("astra.securityHead.title", "Enterprise-grade by design")}
              subtitle={c(
                "astra.securityHead.subtitle",
                "Least privilege, full auditability and human oversight are foundational — not add-ons.",
              )}
            />
          </Reveal>
          <div className="mt-14 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
            {security.map((s, i) => {
              const Icon = securityIcons[i % securityIcons.length];
              return (
                <Reveal key={s.title} delay={i * 0.08}>
                  <div className="h-full rounded-2xl border border-token bg-surface p-6">
                    <div className="grid h-11 w-11 place-items-center rounded-xl bg-brand-500/10 text-brand-500">
                      <Icon className="h-5 w-5" />
                    </div>
                    <h3 className="mt-4 text-base font-bold">{s.title}</h3>
                    <p className="mt-1.5 text-sm leading-relaxed text-secondary-token">
                      {s.desc}
                    </p>
                  </div>
                </Reveal>
              );
            })}
          </div>
        </Container>
      </Section>

      {/* ------------------------------------------------------------ CTA */}
      <Section className="pb-28">
        <Container>
          <Reveal>
            <div className="relative overflow-hidden rounded-3xl border border-token bg-gradient-to-br from-brand-600 to-violet-600 px-8 py-14 text-center sm:px-16">
              <div className="absolute inset-0 grid-bg opacity-20" />
              <div className="relative">
                <h2 className="text-3xl font-bold text-white sm:text-4xl">
                  {c("astra.cta.title", "Deploy ASTRA across your fleet")}
                </h2>
                <p className="mx-auto mt-4 max-w-xl text-white/85">
                  {c(
                    "astra.cta.subtitle",
                    "Get started in minutes, or talk to us about a guided rollout for your organization.",
                  )}
                </p>
                <div className="mt-8 flex flex-wrap justify-center gap-3">
                  <a
                    href={site.appUrl}
                    className="inline-flex items-center gap-2 rounded-xl bg-white px-6 py-3 text-sm font-semibold text-brand-700 transition-transform hover:-translate-y-0.5"
                  >
                    {c("astra.cta.btn1", "Launch ASTRA")}{" "}
                    <ArrowRight className="h-4 w-4" />
                  </a>
                  <a
                    href={bookDemo.href}
                    {...(bookDemo.external ? { target: "_blank", rel: "noopener" } : {})}
                    className="inline-flex items-center gap-2 rounded-xl border border-white/40 px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-white/10"
                  >
                    {c("astra.cta.btn2", "Book a demo")}
                  </a>
                </div>
              </div>
            </div>
          </Reveal>
        </Container>
      </Section>
    </>
  );
}
