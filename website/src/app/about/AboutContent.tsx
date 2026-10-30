"use client";

import { useCallback, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  Server,
  Laptop,
  Cloud,
  CodeXml,
  Globe,
  AppWindow,
  Plug,
  Bot,
  Cpu,
  ShieldCheck,
  Users,
  Target,
  Handshake,
  Rocket,
  Headphones,
  Check,
  Search,
  PenTool,
  Hammer,
  LifeBuoy,
  Building2,
  MapPin,
  ArrowRight,
  Play,
} from "lucide-react";
import { Container, Section, Reveal, Badge, SectionHeading, Button } from "@/components/ui";
import { AnimatedBackground } from "@/components/AnimatedBackground";
import { TiltCard, Counter, Marquee } from "@/components/enhance";
import { TechnomateIntro } from "@/components/three/TechnomateIntro";
import { useContent, Rich } from "@/lib/content";
import { site } from "@/lib/site";
import { cn } from "@/lib/utils";

type Cat = "it" | "dev" | "ai";
type Service = { title: string; desc: string; tags: string[]; cat: Cat };

const serviceIcons = [Server, Laptop, Cloud, CodeXml, Globe, AppWindow, Plug, Cpu, Bot];
const serviceDefaults: Service[] = [
  {
    cat: "it",
    title: "Managed IT Services",
    desc: "Monitoring, patching, helpdesk and security for every device — we run the technology so your team can run the business.",
    tags: ["Helpdesk", "Patching", "Monitoring"],
  },
  {
    cat: "it",
    title: "Laptop & Hardware Supply",
    desc: "Business-grade laptops, desktops, workstations, servers and networking — procured, configured and delivered ready to deploy.",
    tags: ["Laptops", "Servers", "Networking"],
  },
  {
    cat: "it",
    title: "Cloud & DevOps",
    desc: "Hosting, CI/CD pipelines, backups and monitoring on AWS, Google Cloud or Azure — deployed, secured and maintained for you.",
    tags: ["Hosting", "CI/CD", "Backups"],
  },
  {
    cat: "dev",
    title: "Custom Software Development",
    desc: "Software shaped around your process — CRM, billing, inventory, HR and internal tools, built for how your team actually works.",
    tags: ["CRM & ERP", "Automation", "Desktop & cloud"],
  },
  {
    cat: "dev",
    title: "Website Development",
    desc: "Fast, modern, SEO-ready business websites with motion, easy content editing and analytics — designed to turn visitors into customers.",
    tags: ["Corporate sites", "E-commerce", "SEO"],
  },
  {
    cat: "dev",
    title: "Web App Solutions",
    desc: "Customer portals, dashboards, booking systems and SaaS platforms — secure, scalable web apps with logins, roles and APIs.",
    tags: ["Portals", "Dashboards", "SaaS"],
  },
  {
    cat: "dev",
    title: "API & System Integrations",
    desc: "Connect the tools you already use — payment gateways, WhatsApp, email, Google Workspace and Microsoft 365 — so data flows without copy-paste.",
    tags: ["REST APIs", "Payments", "Webhooks"],
  },
  {
    cat: "ai",
    title: "AI-Powered IT Operations",
    desc: "With SAVIO, our own AI System Administrator, issues across your fleet are detected and healed automatically — with human approval where it matters.",
    tags: ["Self-healing", "Telemetry", "Approvals"],
  },
  {
    cat: "ai",
    title: "AI Chatbots & Automation",
    desc: "Assistants for your website and helpdesk, document Q&A and workflow automation that give your team hours back every week.",
    tags: ["Chatbots", "Document AI", "Workflows"],
  },
];

const filters: { key: "all" | Cat; label: string }[] = [
  { key: "all", label: "All services" },
  { key: "it", label: "IT & Hardware" },
  { key: "dev", label: "Software & Web" },
  { key: "ai", label: "AI" },
];

const stepIcons = [Search, PenTool, Hammer, LifeBuoy];
const stepDefaults = [
  { title: "Discover", desc: "We map your requirements, users and goals, then share a clear scope and quote." },
  { title: "Design", desc: "Wireframes and a clickable prototype you approve before a line of code is written." },
  { title: "Build", desc: "Short sprints with a working demo every week — you see progress, not promises." },
  { title: "Launch & support", desc: "Deployment, training and ongoing maintenance so it keeps working as you grow." },
];

const techDefaults = [
  "Next.js", "React", "TypeScript", "Node.js", "Python", "FastAPI",
  ".NET / C#", "PostgreSQL", "Tailwind CSS", "Docker", "Cloud Run", "Three.js",
];

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
  { value: "33", label: "Automated remediation actions" },
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

/** A browser window whose page assembles itself, on a loop. */
function BuildingBrowser() {
  const block = (delay: number) => ({
    initial: { opacity: 0, y: 12, scale: 0.96 },
    animate: { opacity: [0, 1, 1, 0], y: [12, 0, 0, 0], scale: [0.96, 1, 1, 1] },
    transition: { duration: 6, delay, times: [0, 0.12, 0.88, 1], repeat: Infinity, repeatDelay: 0.4 },
  });
  return (
    <div className="glow relative overflow-hidden rounded-2xl border border-token bg-app">
      <div className="flex items-center gap-2 border-b border-token bg-surface px-4 py-3">
        <span className="h-2.5 w-2.5 rounded-full bg-red-400/80" />
        <span className="h-2.5 w-2.5 rounded-full bg-amber-400/80" />
        <span className="h-2.5 w-2.5 rounded-full bg-emerald-400/80" />
        <div className="ml-3 flex-1 truncate rounded-md bg-surface-2 px-3 py-1 text-[11px] text-muted-token">
          https://your-business.com
        </div>
      </div>
      <div className="space-y-4 p-5 sm:p-6">
        <motion.div {...block(0)} className="flex items-center justify-between">
          <div className="h-3 w-20 rounded bg-brand-500/70" />
          <div className="flex gap-2">
            {[0, 1, 2].map((i) => (
              <div key={i} className="h-2 w-10 rounded bg-surface-2" />
            ))}
          </div>
        </motion.div>
        <motion.div {...block(0.35)} className="rounded-xl bg-gradient-to-br from-brand-600/90 to-cyan-500/80 p-5">
          <div className="h-4 w-3/4 rounded bg-white/90" />
          <div className="mt-2 h-4 w-1/2 rounded bg-white/70" />
          <div className="mt-4 h-7 w-24 rounded-lg bg-white" />
        </motion.div>
        <div className="grid grid-cols-3 gap-3">
          {[0, 1, 2].map((i) => (
            <motion.div key={i} {...block(0.7 + i * 0.2)} className="rounded-lg border border-token bg-surface p-3">
              <div className="h-6 w-6 rounded-md bg-brand-500/20" />
              <div className="mt-3 h-2 w-full rounded bg-surface-2" />
              <div className="mt-1.5 h-2 w-2/3 rounded bg-surface-2" />
            </motion.div>
          ))}
        </div>
        <motion.div {...block(1.4)} className="flex items-end gap-1.5 rounded-lg border border-token bg-surface p-3">
          {[40, 65, 50, 80, 60, 95, 75].map((h, i) => (
            <div
              key={i}
              className="flex-1 rounded-sm bg-gradient-to-t from-brand-600 to-cyan-400"
              style={{ height: `${h * 0.5}px` }}
            />
          ))}
        </motion.div>
      </div>
      <motion.div
        aria-hidden
        className="pointer-events-none absolute inset-y-0 w-1/3 bg-gradient-to-r from-transparent via-white/10 to-transparent"
        animate={{ x: ["-120%", "320%"] }}
        transition={{ duration: 3, repeat: Infinity, repeatDelay: 3.4, ease: "easeInOut" }}
      />
    </div>
  );
}

export function AboutContent() {
  const { c, list } = useContent();
  const services = list<Service>("about.services", serviceDefaults);
  const steps = list("about.steps", stepDefaults);
  const tech = list<string>("about.tech", techDefaults);
  const highlights = list<string>("about.highlights", highlightDefaults);
  const values = list("about.values", valueDefaults);
  const stats = list<AStat>("about.stats", statDefaults);
  const [filter, setFilter] = useState<"all" | Cat>("all");
  // intro: the overlay is mounted. revealed: its logo has started flying to the navbar,
  // so the hero can come in underneath while it travels.
  const [intro, setIntro] = useState(true);
  const [revealed, setRevealed] = useState(false);
  const endIntro = useCallback(() => setIntro(false), []);
  const reveal = useCallback(() => setRevealed(true), []);
  // Hero items wait behind the intro, then rise in one after another.
  const heroIn = (delay: number) => ({
    initial: false as const,
    animate: revealed ? { opacity: 1, y: 0 } : { opacity: 0, y: 36 },
    transition: { duration: 0.7, delay: revealed ? 0.3 + delay : 0, ease: [0.21, 0.47, 0.32, 0.98] },
  });

  // Icons follow the default list's order, so match on title, not position.
  const iconFor = (title: string, i: number) => {
    const at = serviceDefaults.findIndex((s) => s.title === title);
    return serviceIcons[(at >= 0 ? at : i) % serviceIcons.length];
  };
  const shown = services.filter((s) => filter === "all" || s.cat === filter);

  return (
    <>
      {/* Intro — the real logo assembles in 3D, then flies into the navbar logo slot. */}
      {intro && <TechnomateIntro onReveal={reveal} onFinish={endIntro} />}
      <noscript>
        <style>{`#tm-intro{display:none}.tm-hero{opacity:1!important;transform:none!important}`}</style>
      </noscript>

      {/* Hero */}
      <section className="aurora grain relative -mt-16 overflow-hidden pt-32 pb-20 sm:pt-40 sm:pb-24">
        <AnimatedBackground />
        <Container className="relative z-10">
          <motion.div {...heroIn(0)} className="tm-hero text-center">
            <Badge>
              <Users className="h-3.5 w-3.5 text-brand-500" /> {c("about.badge", "About Technomate")}
            </Badge>
          </motion.div>
          <motion.div {...heroIn(0.1)} className="tm-hero mx-auto mt-6 max-w-3xl text-center">
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
              <Button href="#services">
                {c("about.heroBtn1", "Explore our services")} <ArrowRight className="h-4 w-4" />
              </Button>
              <Button href="/contact" variant="secondary">
                {c("about.heroBtn2", "Start a project")}
              </Button>
            </div>
            <button
              type="button"
              onClick={() => {
                setRevealed(false);
                setIntro(true);
              }}
              className="mt-6 inline-flex items-center gap-1.5 text-xs font-medium text-muted-token transition hover:text-brand-500"
            >
              <Play className="h-3.5 w-3.5" /> {c("about.replayIntro", "Replay intro")}
            </button>
          </motion.div>
        </Container>
      </section>

      {/* Service marquee */}
      <section className="border-y border-token bg-surface/60 py-5">
        <Marquee duration={32}>
          {services.map((s, i) => {
            const Icon = iconFor(s.title, i);
            return (
              <div key={s.title} className="flex items-center gap-2 whitespace-nowrap text-sm font-medium text-muted-token">
                <Icon className="h-4 w-4 text-brand-500" />
                {s.title}
                <span className="ml-8 h-1 w-1 rounded-full bg-brand-500/40" />
              </div>
            );
          })}
        </Marquee>
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

      {/* Services */}
      <Section id="services" className="relative scroll-mt-20 overflow-hidden bg-surface">
        <div className="grid-bg pointer-events-none absolute inset-0 opacity-50 [mask-image:linear-gradient(to_bottom,black,transparent)]" />
        <Container className="relative">
          <Reveal>
            <SectionHeading
              eyebrow={c("about.servicesHead.eyebrow", "What we do")}
              title={<Rich text={c("about.servicesHead.title", "Services built for [[modern businesses]]")} />}
              subtitle={c(
                "about.servicesHead.subtitle",
                "From the laptop on your desk to the software your customers use — design, build, run and automate, all under one roof.",
              )}
            />
          </Reveal>

          <Reveal delay={0.05}>
            <div className="mt-10 flex flex-wrap justify-center gap-2">
              {filters.map((f) => (
                <button
                  key={f.key}
                  type="button"
                  onClick={() => setFilter(f.key)}
                  className={cn(
                    "relative rounded-full px-4 py-2 text-sm font-medium transition-colors",
                    filter === f.key ? "text-white" : "text-secondary-token hover:text-primary-token",
                  )}
                >
                  {filter === f.key && (
                    <motion.span
                      layoutId="svc-pill"
                      className="absolute inset-0 rounded-full bg-brand-600 shadow-lg shadow-brand-600/30"
                      transition={{ type: "spring", stiffness: 380, damping: 30 }}
                    />
                  )}
                  <span className="relative">{f.label}</span>
                </button>
              ))}
            </div>
          </Reveal>

          <motion.div layout className="mt-10 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            <AnimatePresence mode="popLayout">
              {shown.map((s, i) => {
                const Icon = iconFor(s.title, i);
                return (
                  <motion.div
                    key={s.title}
                    layout
                    initial={{ opacity: 0, scale: 0.92, y: 20 }}
                    animate={{ opacity: 1, scale: 1, y: 0 }}
                    exit={{ opacity: 0, scale: 0.92 }}
                    transition={{ duration: 0.35, delay: i * 0.04 }}
                  >
                    <TiltCard className="h-full rounded-2xl">
                      <div className="ring-conic flex h-full flex-col rounded-2xl border border-token bg-app p-7 transition-shadow group-hover:shadow-xl group-hover:shadow-brand-600/10">
                        <div className="flex items-center justify-between">
                          <div className="grid h-12 w-12 place-items-center rounded-xl bg-gradient-to-br from-brand-600 to-cyan-500 text-white shadow-lg shadow-brand-600/25 transition-transform duration-300 group-hover:-rotate-6 group-hover:scale-110">
                            <Icon className="h-6 w-6" />
                          </div>
                          {s.cat === "dev" && (
                            <span className="rounded-full bg-brand-500/10 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider text-brand-500">
                              Development
                            </span>
                          )}
                        </div>
                        <h3 className="mt-5 text-lg font-bold">{s.title}</h3>
                        <p className="mt-2 flex-1 text-sm leading-relaxed text-secondary-token">{s.desc}</p>
                        <div className="mt-5 flex flex-wrap gap-2">
                          {s.tags.map((t) => (
                            <span key={t} className="rounded-md border border-token bg-surface px-2 py-1 text-[11px] text-muted-token">
                              {t}
                            </span>
                          ))}
                        </div>
                      </div>
                    </TiltCard>
                  </motion.div>
                );
              })}
            </AnimatePresence>
          </motion.div>
          <div className="mt-10 text-center">
            <Button href="/services">
              {c("about.servicesBtn", "Explore all services")} <ArrowRight className="h-4 w-4" />
            </Button>
          </div>
        </Container>
      </Section>

      {/* Software & web development spotlight */}
      <Section>
        <Container>
          <div className="grid items-center gap-12 lg:grid-cols-2">
            <Reveal>
              <span className="text-sm font-semibold uppercase tracking-wider text-brand-500">
                {c("about.devEyebrow", "Software & web development")}
              </span>
              <h2 className="mt-3 text-3xl font-bold tracking-tight sm:text-4xl">
                <Rich text={c("about.devTitle", "Software that fits [[the way you work]]")} />
              </h2>
              <p className="mt-5 leading-relaxed text-secondary-token">
                {c(
                  "about.devText",
                  "Off-the-shelf tools make you change your process to fit them. We do the opposite — custom software, websites and web apps designed around your business, built on the same modern stack we use for SAVIO itself.",
                )}
              </p>
              <div className="mt-7 flex flex-wrap gap-2">
                {tech.map((t, i) => (
                  <motion.span
                    key={t}
                    initial={{ opacity: 0, scale: 0.8 }}
                    whileInView={{ opacity: 1, scale: 1 }}
                    viewport={{ once: true }}
                    transition={{ delay: i * 0.04 }}
                    whileHover={{ y: -3 }}
                    className="rounded-full border border-token bg-surface px-3 py-1.5 text-xs font-medium text-secondary-token hover:border-brand-500/50 hover:text-brand-500"
                  >
                    {t}
                  </motion.span>
                ))}
              </div>
              <div className="mt-8">
                <Button href="/contact">
                  {c("about.devBtn", "Discuss your project")} <ArrowRight className="h-4 w-4" />
                </Button>
              </div>
            </Reveal>
            <Reveal delay={0.1}>
              <BuildingBrowser />
            </Reveal>
          </div>

          {/* Process */}
          <div className="relative mt-20">
            <motion.div
              aria-hidden
              initial={{ scaleX: 0 }}
              whileInView={{ scaleX: 1 }}
              viewport={{ once: true, margin: "-100px" }}
              transition={{ duration: 1.4, ease: "easeInOut" }}
              className="absolute left-[12.5%] right-[12.5%] top-7 hidden h-px origin-left bg-gradient-to-r from-brand-600 via-brand-400 to-cyan-400 lg:block"
            />
            <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
              {steps.map((s, i) => {
                const Icon = stepIcons[i % stepIcons.length];
                return (
                  <Reveal key={s.title} delay={0.2 + i * 0.15} className="relative text-center">
                    <div className="relative mx-auto grid h-14 w-14 place-items-center rounded-2xl border border-token bg-surface text-brand-500 shadow-lg shadow-brand-600/10">
                      <Icon className="h-6 w-6" />
                      <span className="absolute -right-2 -top-2 grid h-6 w-6 place-items-center rounded-full bg-brand-600 text-[11px] font-bold text-white">
                        {i + 1}
                      </span>
                    </div>
                    <h4 className="mt-4 font-bold">{s.title}</h4>
                    <p className="mt-1 text-sm leading-relaxed text-secondary-token">{s.desc}</p>
                  </Reveal>
                );
              })}
            </div>
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
