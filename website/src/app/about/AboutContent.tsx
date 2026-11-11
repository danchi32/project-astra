"use client";

import { motion } from "framer-motion";
import {
  ShieldCheck,
  Users,
  Target,
  Handshake,
  Rocket,
  Headphones,
  Check,
  Building2,
  MapPin,
  ArrowRight,
} from "lucide-react";
import { Container, Section, Reveal, Badge, Button } from "@/components/ui";
import { AnimatedBackground } from "@/components/AnimatedBackground";
import { Counter } from "@/components/enhance";
import { useContent, Rich } from "@/lib/content";
import { site } from "@/lib/site";
import { cn } from "@/lib/utils";

const highlightDefaults = [
  "One accountable partner for IT, hardware, software and AI",
  "Our own AI platform, SAVIO, built and run in-house",
  "Custom software and web apps designed around your workflow",
  "India-based team — fast response, clear communication",
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
  { value: "35", label: "Automated remediation actions" },
  { value: "3", label: "Approval tiers, enforced in code" },
  { value: "60s", label: "Telemetry from every device" },
  { value: "24/7", label: "Monitoring with SAVIO" },
];

/** "60s" → count up to 60 then "s"; anything not starting with a number renders as-is. */
function StatValue({ value }: { value: string }) {
  const m = /^(\d+)(.*)$/.exec(value);
  if (!m) return <>{value}</>;
  return <Counter value={Number(m[1])} suffix={m[2]} />;
}

export function AboutContent() {
  const { c, list } = useContent();
  const highlights = list<string>("about.highlights", highlightDefaults);
  const values = list("about.values", valueDefaults);
  const stats = list<AStat>("about.stats", statDefaults);

  return (
    <>
      {/* Hero */}
      <section className="aurora grain relative -mt-16 overflow-hidden pt-32 pb-20 sm:pt-40 sm:pb-24">
        <AnimatedBackground />
        <Container className="relative z-10">
          <Reveal className="text-center">
            <Badge>
              <Users className="h-3.5 w-3.5 text-brand-500" /> {c("about.badge", "About Technomate")}
            </Badge>
          </Reveal>
          <Reveal delay={0.1} className="mx-auto mt-6 max-w-3xl text-center">
            <h1 className="text-4xl font-extrabold leading-tight tracking-tight sm:text-6xl">
              <Rich text={c("about.title", "Your technology partner for [[IT, software & AI]]")} />
            </h1>
            <p className="mt-6 text-lg leading-relaxed text-secondary-token">
              <Rich
                text={c(
                  "about.subtitle",
                  "Technomate IT-Solution is an IT services, hardware and software development company. We keep your systems running, supply the hardware behind them, build the custom software, websites and web apps your business runs on — and automate day-to-day IT with our own AI System Administrator, **SAVIO**.",
                )}
              />
            </p>
            <div className="mt-8 flex flex-wrap justify-center gap-3">
              <Button href="/services">
                {c("about.heroBtn1", "Explore our services")} <ArrowRight className="h-4 w-4" />
              </Button>
              <Button href="/contact" variant="secondary">
                {c("about.heroBtn2", "Start a project")}
              </Button>
            </div>
          </Reveal>
        </Container>
      </section>

      {/* Who we are */}
      <Section>
        <Container>
          <div className="grid items-center gap-12 lg:grid-cols-2">
            <Reveal>
              <span className="text-sm font-semibold uppercase tracking-wider text-brand-500">
                {c("about.storyEyebrow", "Who we are")}
              </span>
              <h2 className="mt-3 text-3xl font-bold tracking-tight sm:text-4xl">
                <Rich text={c("about.storyTitle", "One partner for your [[entire technology stack]]")} />
              </h2>
              <p className="mt-5 leading-relaxed text-secondary-token">
                {c(
                  "about.storyText1",
                  "Technomate IT-Solution helps growing businesses run on reliable, secure and modern technology. We started with what every office needs — managed IT support and the right hardware — and grew into building the software that runs on it.",
                )}
              </p>
              <p className="mt-4 leading-relaxed text-secondary-token">
                {c(
                  "about.storyText2",
                  "Today our team designs custom software, business websites and web applications, and builds SAVIO — an AI System Administrator that detects and fixes IT problems before your people notice them. Our promise is simple: automate today, innovate tomorrow.",
                )}
              </p>
              <ul className="mt-7 space-y-3">
                {highlights.map((h, i) => (
                  <motion.li
                    key={h}
                    initial={{ opacity: 0, x: -16 }}
                    whileInView={{ opacity: 1, x: 0 }}
                    viewport={{ once: true }}
                    transition={{ delay: 0.15 + i * 0.1 }}
                    className="flex items-start gap-3 text-sm"
                  >
                    <span className="mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full bg-brand-500/15 text-brand-500">
                      <Check className="h-3 w-3" />
                    </span>
                    {h}
                  </motion.li>
                ))}
              </ul>
            </Reveal>
            <Reveal delay={0.1}>
              <div className="grid grid-cols-2 gap-4">
                {stats.map((s, i) => (
                  <motion.div
                    key={s.label}
                    whileHover={{ y: -4 }}
                    className={cn(
                      "ring-conic rounded-2xl border border-token bg-surface p-6",
                      i % 2 === 1 && "sm:translate-y-6",
                    )}
                  >
                    <div className="text-3xl font-extrabold gradient-text sm:text-4xl">
                      <StatValue value={s.value} />
                    </div>
                    <div className="mt-1 text-xs text-muted-token sm:text-sm">{s.label}</div>
                  </motion.div>
                ))}
                <div className="col-span-2 mt-2 flex flex-wrap items-center gap-x-6 gap-y-2 rounded-2xl border border-token bg-surface-2 px-5 py-4 text-xs text-secondary-token sm:mt-8">
                  <span className="flex items-center gap-2">
                    <Building2 className="h-4 w-4 text-brand-500" /> {site.legal.displayName}
                  </span>
                  <span className="flex items-center gap-2">
                    <MapPin className="h-4 w-4 text-brand-500" /> {site.legal.registeredOffice[1]}, Uttar Pradesh, India
                  </span>
                </div>
              </div>
            </Reveal>
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
                    "Great IT shouldn't require a large in-house team. By combining hands-on service, quality hardware and SAVIO's AI automation, we give growing organizations the same resilience the largest enterprises enjoy — without the overhead.",
                  )}
                </p>
                <div className="mt-6 flex flex-wrap gap-3">
                  <Button href="/savio">
                    {c("about.missionBtn1", "Discover SAVIO")}
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
                    <motion.div
                      key={v.title}
                      whileHover={{ y: -4 }}
                      className="rounded-2xl border border-token bg-app p-5 transition-colors hover:border-brand-500/40"
                    >
                      <Icon className="h-6 w-6 text-brand-500" />
                      <h4 className="mt-3 text-sm font-bold">{v.title}</h4>
                      <p className="mt-1 text-xs leading-relaxed text-secondary-token">
                        {v.desc}
                      </p>
                    </motion.div>
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
            <div className="aurora relative flex flex-col items-center gap-4 overflow-hidden rounded-3xl border border-token bg-surface px-8 py-14 text-center">
              <motion.div
                animate={{ y: [0, -8, 0] }}
                transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
              >
                <Headphones className="h-10 w-10 text-brand-500" />
              </motion.div>
              <h2 className="text-2xl font-bold sm:text-3xl">
                {c("about.supportTitle", "Talk to a human — backed by an AI")}
              </h2>
              <p className="max-w-xl text-secondary-token">
                {c(
                  "about.supportText",
                  "Whether you need a fleet of laptops, managed support, a custom software project, a new website or a demo of SAVIO, our team is ready to help.",
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
