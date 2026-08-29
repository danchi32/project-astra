"use client";

import {
  Server,
  Laptop,
  ShieldCheck,
  Users,
  Target,
  Handshake,
  Rocket,
  Cpu,
  Headphones,
} from "lucide-react";
import { Container, Section, Reveal, Badge, SectionHeading, Button } from "@/components/ui";
import { AnimatedBackground } from "@/components/AnimatedBackground";
import { useContent, Rich } from "@/lib/content";

const offeringIcons = [Server, Laptop, Cpu];
const offeringDefaults = [
  {
    title: "IT Service Provider",
    desc: "Managed IT support, monitoring, patching, security and helpdesk — we run the technology so your team can run the business.",
  },
  {
    title: "Laptop & Hardware Supplier",
    desc: "Business-grade laptops, desktops, workstations, servers and networking — procured, configured and delivered ready to deploy.",
  },
  {
    title: "AI-Powered Operations",
    desc: "With ASTRA, we bring AI-driven automation to IT support — detecting and healing issues across your fleet automatically.",
  },
];

const valueIcons = [Target, Handshake, ShieldCheck, Rocket];
const valueDefaults = [
  { title: "Reliability first", desc: "Uptime and continuity drive every decision we make." },
  { title: "True partnership", desc: "We act as an extension of your team, not a vendor at arm's length." },
  { title: "Security by default", desc: "Least privilege, auditability and human oversight, always on." },
  { title: "Innovation", desc: "We invest in AI and automation so our clients stay ahead." },
];

type AStat = { value: string; label: string };
const statDefaults: AStat[] = [
  // Kept in step with backend/app/services/remediation/actions.py by
  // backend/tests/test_website_numbers.py. It said 23 while the registry held 29.
  { value: "29", label: "Automated remediation actions" },
  { value: "3", label: "Approval tiers, enforced in code" },
  { value: "60s", label: "Telemetry from every device" },
  { value: "24/7", label: "Monitoring with ASTRA" },
];

export function AboutContent() {
  const { c, list } = useContent();
  const offerings = list("about.offerings", offeringDefaults);
  const values = list("about.values", valueDefaults);
  const stats = list<AStat>("about.stats", statDefaults);

  return (
    <>
      <section className="aurora grain relative -mt-16 overflow-hidden pt-28 pb-16 sm:pt-36">
        <AnimatedBackground />
        <Container>
          <Reveal>
            <Badge>
              <Users className="h-3.5 w-3.5 text-brand-500" />{" "}
              {c("about.badge", "About Technomate")}
            </Badge>
          </Reveal>
          <Reveal delay={0.05}>
            <h1 className="mt-5 max-w-3xl text-4xl font-extrabold leading-tight tracking-tight sm:text-5xl">
              <Rich
                text={c(
                  "about.title",
                  "Your technology partner for [[services, hardware & AI]]",
                )}
              />
            </h1>
          </Reveal>
          <Reveal delay={0.1}>
            <p className="mt-6 max-w-2xl text-lg leading-relaxed text-secondary-token">
              <Rich
                text={c(
                  "about.subtitle",
                  "Technomate IT-Solution is an IT service provider and hardware supplier. We help organizations run reliable, secure IT — from sourcing the right laptops and infrastructure to managing and automating day-to-day operations with our own AI System Administrator, **ASTRA**.",
                )}
              />
            </p>
          </Reveal>
        </Container>
      </section>

      {/* Stats */}
      <Section className="py-12">
        <Container>
          <Reveal>
            <div className="grid grid-cols-2 gap-4 rounded-2xl border border-token bg-surface p-6 sm:grid-cols-4 sm:p-8">
              {stats.map((s) => (
                <div key={s.label} className="text-center">
                  <div className="text-3xl font-extrabold gradient-text sm:text-4xl">
                    {s.value}
                  </div>
                  <div className="mt-1 text-xs text-muted-token sm:text-sm">
                    {s.label}
                  </div>
                </div>
              ))}
            </div>
          </Reveal>
        </Container>
      </Section>

      {/* What we do */}
      <Section>
        <Container>
          <Reveal>
            <SectionHeading
              eyebrow={c("about.whoHead.eyebrow", "Who we are")}
              title={c("about.whoHead.title", "Two things done exceptionally well")}
              subtitle={c(
                "about.whoHead.subtitle",
                "We provide IT services and we supply the hardware behind them — a single accountable partner for your whole environment.",
              )}
            />
          </Reveal>
          <div className="mt-14 grid gap-6 md:grid-cols-3">
            {offerings.map((o, i) => {
              const Icon = offeringIcons[i % offeringIcons.length];
              return (
                <Reveal key={o.title} delay={i * 0.1}>
                  <div className="h-full rounded-2xl border border-token bg-surface p-7 transition-all hover:-translate-y-1 hover:border-brand-500/40 hover:shadow-xl">
                    <div className="grid h-12 w-12 place-items-center rounded-xl bg-brand-500/10 text-brand-500">
                      <Icon className="h-6 w-6" />
                    </div>
                    <h3 className="mt-5 text-lg font-bold">{o.title}</h3>
                    <p className="mt-2 text-sm leading-relaxed text-secondary-token">
                      {o.desc}
                    </p>
                  </div>
                </Reveal>
              );
            })}
          </div>
        </Container>
      </Section>

      {/* Mission */}
      <Section className="bg-surface">
        <Container>
          <div className="grid items-center gap-12 lg:grid-cols-2">
            <Reveal>
              <div>
                <span className="text-sm font-semibold uppercase tracking-wider text-brand-500">
                  {c("about.missionEyebrow", "Our mission")}
                </span>
                <h2 className="mt-3 text-3xl font-bold tracking-tight sm:text-4xl">
                  {c("about.missionTitle", "Make enterprise-grade IT effortless for every business")}
                </h2>
                <p className="mt-4 text-secondary-token">
                  {c(
                    "about.missionText",
                    "Great IT shouldn't require a large in-house team. By combining hands-on service, quality hardware and ASTRA's AI automation, we give growing organizations the same resilience the largest enterprises enjoy — without the overhead.",
                  )}
                </p>
                <div className="mt-6 flex flex-wrap gap-3">
                  <Button href="/astra">
                    {c("about.missionBtn1", "Discover ASTRA")}
                  </Button>
                  <Button href="/contact" variant="secondary">
                    {c("about.missionBtn2", "Work with us")}
                  </Button>
                </div>
              </div>
            </Reveal>
            <Reveal delay={0.1}>
              <div className="grid gap-4 sm:grid-cols-2">
                {values.map((v, i) => {
                  const Icon = valueIcons[i % valueIcons.length];
                  return (
                    <div
                      key={v.title}
                      className="rounded-2xl border border-token bg-app p-5"
                    >
                      <Icon className="h-6 w-6 text-brand-500" />
                      <h4 className="mt-3 text-sm font-bold">{v.title}</h4>
                      <p className="mt-1 text-xs leading-relaxed text-secondary-token">
                        {v.desc}
                      </p>
                    </div>
                  );
                })}
              </div>
            </Reveal>
          </div>
        </Container>
      </Section>

      {/* Support band */}
      <Section className="pb-28">
        <Container>
          <Reveal>
            <div className="flex flex-col items-center gap-4 rounded-3xl border border-token bg-surface px-8 py-12 text-center">
              <Headphones className="h-10 w-10 text-brand-500" />
              <h2 className="text-2xl font-bold sm:text-3xl">
                {c("about.supportTitle", "Talk to a human — backed by an AI")}
              </h2>
              <p className="max-w-xl text-secondary-token">
                {c(
                  "about.supportText",
                  "Whether you need a fleet of laptops, managed support, or a demo of ASTRA, our team is ready to help.",
                )}
              </p>
              <Button href="/contact">{c("about.supportBtn", "Contact us")}</Button>
            </div>
          </Reveal>
        </Container>
      </Section>
    </>
  );
}
