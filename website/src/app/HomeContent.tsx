"use client";

import Link from "next/link";
import {
  ArrowRight,
  Sparkles,
  Server,
  Laptop,
  Wrench,
  ShieldCheck,
  Boxes,
  Activity,
  Gauge,
  BrainCircuit,
  CheckCircle2,
  DownloadCloud,
  UserX,
} from "lucide-react";
import { Container, Section, Reveal, Button, Badge, SectionHeading } from "@/components/ui";
import { AnimatedBackground } from "@/components/AnimatedBackground";
import { DashboardMockup, AiConsole, SelfHealingFlow } from "@/components/visuals";
import { TiltCard, Counter, Magnetic, Marquee } from "@/components/enhance";
import { Hero3D } from "@/components/three/Hero3D";
import { useContent, Rich } from "@/lib/content";
import { site } from "@/lib/site";

const pillarIcons = [Server, Laptop, Sparkles];
const pillarDefaults = [
  {
    title: "Managed IT Services",
    desc: "Proactive support, monitoring, patching and helpdesk that keep your workforce productive — on-site and remote.",
  },
  {
    title: "Laptops & Hardware",
    desc: "Business-grade laptops, desktops, workstations and networking gear — sourced, configured and delivered ready to work.",
  },
  {
    title: "ASTRA — AI System Admin",
    desc: "Our AI IT agent that watches every device, diagnoses issues, and self-heals them — with human approval where it matters.",
  },
];

const capIcons = [Boxes, Wrench, Activity, DownloadCloud, UserX, BrainCircuit, ShieldCheck, Gauge];
const capDefaults = [
  "Asset Inventory",
  "Self-Healing",
  "Live Telemetry",
  "Patch Management",
  "Secure Offboarding",
  "AI Reasoning",
  "Approval Tiers",
  "Real-time Dashboards",
  "Compliance",
  "Helpdesk Escalation",
  "Self-Learning KB",
];

type Stat = { value: number; suffix?: string; decimals?: number; label: string };
const statDefaults: Stat[] = [
  { value: 1204, suffix: "+", label: "Issues auto-healed / mo" },
  { value: 38, suffix: "s", label: "Avg. resolution time" },
  { value: 72, suffix: "%", label: "Less manual triage" },
  { value: 99.9, decimals: 1, suffix: "%", label: "Fleet visibility" },
];

export function HomeContent() {
  const { c, list } = useContent();
  const pillars = list("home.pillars", pillarDefaults);
  const marquee = list<string>("home.marquee", capDefaults);
  const stats = list<Stat>("home.stats", statDefaults);
  const heroChecks = list<string>("home.hero.checks", [
    "No manual triage",
    "Human-in-the-loop",
    "Least privilege",
  ]);
  const consoleBullets = list<string>("home.console.bullets", [
    "Live device health & telemetry",
    "ASTRA activity stream in real time",
    "Drill into any endpoint instantly",
  ]);
  const teaserBullets = list<string>("home.teaser.bullets", [
    "Understands issues in plain language",
    "Collects live telemetry across the fleet",
    "Self-heals with tiered approval controls",
    "Verifies and learns from every resolution",
  ]);

  return (
    <>
      {/* ------------------------------------------------------------ HERO */}
      {/* Pulled up by the header's height so the aurora starts at the very top
          of the page and washes behind the (transparent) header. The top
          padding absorbs that shift, keeping content where it was. */}
      <section className="aurora grain relative -mt-16 overflow-hidden pt-28 pb-20 sm:pt-36">
        <AnimatedBackground dense />
        <Container>
          <div className="grid items-center gap-12 lg:grid-cols-2">
            <div>
              <Reveal>
                <Badge>
                  <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-500" />
                  {c("home.hero.badge", "IT Services · Hardware · AI Automation")}
                </Badge>
              </Reveal>
              <Reveal delay={0.05}>
                <h1 className="mt-5 text-4xl font-extrabold leading-[1.08] tracking-tight sm:text-5xl lg:text-6xl">
                  <Rich
                    text={c(
                      "home.hero.title",
                      "IT that runs itself,\npowered by [[ASTRA AI]]",
                    )}
                  />
                </h1>
              </Reveal>
              <Reveal delay={0.1}>
                <p className="mt-6 max-w-xl text-lg leading-relaxed text-secondary-token">
                  <Rich
                    text={c(
                      "home.hero.subtitle",
                      "Technomate IT-Solution delivers managed IT services and business hardware — supercharged by **ASTRA**, an AI System Administrator that detects, diagnoses and heals IT issues before your team even notices.",
                    )}
                  />
                </p>
              </Reveal>
              <Reveal delay={0.15}>
                <div className="mt-8 flex flex-wrap items-center gap-3">
                  <Magnetic>
                    <Button href="/astra">
                      {c("home.hero.cta1", "Explore ASTRA")}{" "}
                      <ArrowRight className="h-4 w-4" />
                    </Button>
                  </Magnetic>
                  <Button href={site.appUrl} variant="secondary" external>
                    {c("home.hero.cta2", "Sign up free")}
                  </Button>
                </div>
              </Reveal>
              <Reveal delay={0.2}>
                <div className="mt-8 flex flex-wrap gap-x-6 gap-y-2 text-sm text-muted-token">
                  {heroChecks.map((t) => (
                    <span key={t} className="flex items-center gap-1.5">
                      <CheckCircle2 className="h-4 w-4 text-emerald-500" />
                      {t}
                    </span>
                  ))}
                </div>
              </Reveal>
            </div>

            {/* 3D ASTRA core */}
            <Reveal delay={0.15} className="flex justify-center">
              <Hero3D />
            </Reveal>
          </div>

          {/* Capability marquee */}
          <Reveal delay={0.25}>
            <div className="mt-16 border-y border-token py-6">
              <Marquee>
                {marquee.map((label, i) => {
                  const Icon = capIcons[i % capIcons.length];
                  return (
                    <div
                      key={label}
                      className="flex items-center gap-2 whitespace-nowrap text-sm font-medium text-muted-token"
                    >
                      <Icon className="h-4 w-4 text-brand-500" />
                      {label}
                      <span className="ml-8 h-1 w-1 rounded-full bg-brand-500/40" />
                    </div>
                  );
                })}
              </Marquee>
            </div>
          </Reveal>
        </Container>
      </section>

      {/* --------------------------------------------------------- STATS */}
      <Section className="py-14">
        <Container>
          <Reveal>
            <div className="grid grid-cols-2 gap-4 rounded-3xl border border-token bg-surface p-8 sm:grid-cols-4">
              {stats.map((s) => (
                <div key={s.label} className="text-center">
                  <div className="text-3xl font-extrabold gradient-text sm:text-4xl">
                    <Counter
                      value={s.value}
                      suffix={s.suffix ?? ""}
                      decimals={s.decimals ?? 0}
                    />
                  </div>
                  <div className="mt-1.5 text-xs text-muted-token sm:text-sm">
                    {s.label}
                  </div>
                </div>
              ))}
            </div>
          </Reveal>
        </Container>
      </Section>

      {/* -------------------------------------------------------- PILLARS */}
      <Section className="pt-6">
        <Container>
          <Reveal>
            <SectionHeading
              eyebrow={c("home.pillarsHead.eyebrow", "What we do")}
              title={c("home.pillarsHead.title", "One partner for your entire IT stack")}
              subtitle={c(
                "home.pillarsHead.subtitle",
                "From the laptop on the desk to the AI that keeps it running — Technomate covers it end to end.",
              )}
            />
          </Reveal>
          <div className="mt-14 grid gap-6 md:grid-cols-3">
            {pillars.map((p, i) => {
              const Icon = pillarIcons[i % pillarIcons.length];
              return (
                <Reveal key={p.title} delay={i * 0.1}>
                  <TiltCard className="h-full">
                    <div className="ring-conic h-full rounded-2xl border border-token bg-surface p-7 transition-all hover:border-brand-500/40 hover:shadow-xl">
                      <div className="grid h-12 w-12 place-items-center rounded-xl bg-brand-500/10 text-brand-500">
                        <Icon className="h-6 w-6" />
                      </div>
                      <h3 className="mt-5 text-lg font-bold">{p.title}</h3>
                      <p className="mt-2 text-sm leading-relaxed text-secondary-token">
                        {p.desc}
                      </p>
                    </div>
                  </TiltCard>
                </Reveal>
              );
            })}
          </div>
        </Container>
      </Section>

      {/* ------------------------------------------------- DASHBOARD PREVIEW */}
      <Section className="bg-surface">
        <Container>
          <div className="grid items-center gap-12 lg:grid-cols-2">
            <Reveal>
              <div>
                <Badge>
                  <Gauge className="h-3.5 w-3.5 text-brand-500" />{" "}
                  {c("home.console.badge", "One console")}
                </Badge>
                <h2 className="mt-5 text-3xl font-bold tracking-tight sm:text-4xl">
                  <Rich
                    text={c("home.console.title", "Your whole fleet, [[one live view]]")}
                  />
                </h2>
                <p className="mt-4 text-secondary-token">
                  {c(
                    "home.console.subtitle",
                    "Every device, every metric, every action ASTRA takes — in a single real-time dashboard built for IT teams that would rather prevent tickets than chase them.",
                  )}
                </p>
                <ul className="mt-6 space-y-3">
                  {consoleBullets.map((t) => (
                    <li key={t} className="flex items-start gap-3">
                      <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-500" />
                      <span className="text-sm text-secondary-token">{t}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </Reveal>
            <Reveal delay={0.1} className="animate-float">
              <DashboardMockup />
            </Reveal>
          </div>
        </Container>
      </Section>

      {/* ---------------------------------------------------- ASTRA TEASER */}
      <Section>
        <Container>
          <div className="grid items-center gap-12 lg:grid-cols-2">
            <Reveal>
              <AiConsole />
            </Reveal>
            <div>
              <Reveal>
                <Badge>
                  <Sparkles className="h-3.5 w-3.5 text-brand-500" />{" "}
                  {c("home.teaser.badge", "Meet ASTRA")}
                </Badge>
              </Reveal>
              <Reveal delay={0.05}>
                <h2 className="mt-5 text-3xl font-bold tracking-tight sm:text-4xl">
                  <Rich
                    text={c(
                      "home.teaser.title",
                      "An AI teammate that fixes IT, [[not just tickets]]",
                    )}
                  />
                </h2>
              </Reveal>
              <Reveal delay={0.1}>
                <p className="mt-4 text-secondary-token">
                  {c(
                    "home.teaser.subtitle",
                    "ASTRA follows a disciplined loop — gather evidence, reason, act, verify — so every fix is grounded in real telemetry and your enterprise knowledge, never guesswork.",
                  )}
                </p>
              </Reveal>
              <Reveal delay={0.15}>
                <ul className="mt-6 space-y-3">
                  {teaserBullets.map((t) => (
                    <li key={t} className="flex items-start gap-3">
                      <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-500" />
                      <span className="text-sm text-secondary-token">{t}</span>
                    </li>
                  ))}
                </ul>
              </Reveal>
              <Reveal delay={0.2}>
                <div className="mt-8">
                  <Magnetic>
                    <Button href="/astra">
                      {c("home.teaser.cta", "See everything ASTRA does")}{" "}
                      <ArrowRight className="h-4 w-4" />
                    </Button>
                  </Magnetic>
                </div>
              </Reveal>
            </div>
          </div>
        </Container>
      </Section>

      {/* --------------------------------------------------- SELF-HEALING */}
      <Section className="bg-surface">
        <Container>
          <Reveal>
            <SectionHeading
              eyebrow={c("home.healingHead.eyebrow", "How ASTRA heals")}
              title={c("home.healingHead.title", "Evidence before action — every single time")}
              subtitle={c(
                "home.healingHead.subtitle",
                "A transparent, auditable pipeline runs behind each resolution.",
              )}
            />
          </Reveal>
          <Reveal delay={0.1}>
            <div className="mt-12">
              <SelfHealingFlow />
            </div>
          </Reveal>
        </Container>
      </Section>

      {/* --------------------------------------------------------- CTA */}
      <Section className="pb-28">
        <Container>
          <Reveal>
            <div className="grain relative overflow-hidden rounded-3xl border border-token bg-gradient-to-br from-brand-600 to-violet-600 px-8 py-14 text-center sm:px-16">
              <div className="absolute inset-0 grid-bg opacity-20" />
              <div className="relative">
                <h2 className="text-3xl font-bold text-white sm:text-4xl">
                  {c("home.cta.title", "Ready to put your IT on autopilot?")}
                </h2>
                <p className="mx-auto mt-4 max-w-xl text-white/85">
                  {c(
                    "home.cta.subtitle",
                    "Talk to our team about managed IT, hardware, and deploying ASTRA across your organization.",
                  )}
                </p>
                <div className="mt-8 flex flex-wrap justify-center gap-3">
                  <Magnetic>
                    <Link
                      href="/contact"
                      className="inline-flex items-center gap-2 rounded-xl bg-white px-6 py-3 text-sm font-semibold text-brand-700 transition-transform hover:-translate-y-0.5"
                    >
                      {c("home.cta.btn1", "Get in touch")}{" "}
                      <ArrowRight className="h-4 w-4" />
                    </Link>
                  </Magnetic>
                  <a
                    href={site.appUrl}
                    className="inline-flex items-center gap-2 rounded-xl border border-white/40 px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-white/10"
                  >
                    {c("home.cta.btn2", "Launch ASTRA")}
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
