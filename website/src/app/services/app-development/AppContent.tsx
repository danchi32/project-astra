"use client";

import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowRight, Check, Smartphone, Apple, Globe, Bell, Lock, Plug, Cloud } from "lucide-react";
import { Container, Section, Reveal, SectionHeading, Button } from "@/components/ui";
import { TiltCard } from "@/components/enhance";
import { PhoneMockup } from "@/components/PhoneMockup";
import { appDemos, customSoftware, quoteHref } from "@/lib/services";
import { cn } from "@/lib/utils";
import { ServiceHero, MiniFeatures, QuoteBand } from "../shared";

const AUTO_MS = 3200;

const capabilities = [
  { icon: Smartphone, title: "Android & iOS", desc: "Native-quality apps from one codebase, published to both stores." },
  { icon: Globe, title: "Web & admin panels", desc: "A dashboard for your team to manage everything the app does." },
  { icon: Bell, title: "Notifications", desc: "Push, SMS, email and WhatsApp alerts that bring users back." },
  { icon: Lock, title: "Secure by design", desc: "Logins, roles, encryption and audit trails from day one." },
  { icon: Plug, title: "Integrations", desc: "Payments, maps, Tally, CRMs and your existing systems." },
  { icon: Cloud, title: "Cloud hosting", desc: "Scalable hosting, backups and monitoring included." },
  { icon: Apple, title: "Store publishing", desc: "We handle Play Store and App Store listings and reviews." },
  { icon: Check, title: "Support & updates", desc: "Bug fixes, OS updates and new features after launch." },
];

export function AppContent() {
  const [active, setActive] = useState(0);
  const [tab, setTab] = useState(0);
  const [auto, setAuto] = useState(true);
  const app = appDemos[active];

  // Walk through the screens on its own until the visitor takes over.
  useEffect(() => {
    if (!auto) return;
    const id = window.setInterval(() => setTab((t) => (t + 1) % app.screens.length), AUTO_MS);
    return () => window.clearInterval(id);
  }, [auto, app]);

  const pick = (i: number) => {
    setActive(i);
    setTab(0);
  };

  return (
    <>
      <ServiceHero
        icon={Smartphone}
        crumb="App & Custom Software"
        badge="App & custom software development"
        title="Apps your customers love and [[software your team relies on]]"
        sub="Android, iOS and web apps plus custom business software — designed around your process. Try the live demos below."
      >
        <Button href="#demos">
          Try the app demos <ArrowRight className="h-4 w-4" />
        </Button>
        <Button href={quoteHref("App Development", "I'd like a custom app for my business.")} variant="secondary">
          Discuss your app idea
        </Button>
      </ServiceHero>

      <Section id="demos" className="scroll-mt-20">
        <Container>
          <Reveal>
            <SectionHeading
              eyebrow="Live demos"
              title="Customisable apps we can build for you"
              subtitle="Tap an app, then use the tabs inside the phone. Each one is a starting point — we adapt the screens, features and branding to your business."
            />
          </Reveal>

          <div className="mt-14 grid items-start gap-10 lg:grid-cols-[1fr_auto_1fr]">
            {/* App picker */}
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-1">
              {appDemos.map((a, i) => (
                <button
                  key={a.slug}
                  type="button"
                  onClick={() => pick(i)}
                  className={cn(
                    "group flex items-center gap-4 rounded-2xl border p-4 text-left transition-all",
                    i === active
                      ? "border-brand-500/60 bg-surface shadow-xl shadow-brand-600/10"
                      : "border-token bg-surface/60 hover:border-brand-500/30 hover:bg-surface",
                  )}
                >
                  <span
                    className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl text-white shadow-lg transition-transform group-hover:scale-105"
                    style={{ background: `linear-gradient(135deg, ${a.from}, ${a.to})` }}
                  >
                    <a.icon className="h-6 w-6" />
                  </span>
                  <span className="min-w-0">
                    <span className="block font-bold">{a.name}</span>
                    <span className="block truncate text-xs text-muted-token">{a.industry}</span>
                  </span>
                  {i === active && <motion.span layoutId="app-dot" className="ml-auto h-2 w-2 shrink-0 rounded-full bg-brand-500" />}
                </button>
              ))}
            </div>

            {/* Phone */}
            <Reveal className="relative">
              <div
                className="pointer-events-none absolute left-1/2 top-1/2 h-80 w-80 -translate-x-1/2 -translate-y-1/2 rounded-full opacity-40 blur-3xl transition-colors duration-700"
                style={{ background: `linear-gradient(135deg, ${app.from}, ${app.to})` }}
              />
              <motion.div animate={{ y: [0, -8, 0] }} transition={{ duration: 5, repeat: Infinity, ease: "easeInOut" }}>
                <PhoneMockup
                  app={app}
                  tab={tab}
                  onTab={(i) => {
                    setAuto(false);
                    setTab(i);
                  }}
                />
              </motion.div>
              <div className="mt-5 flex justify-center gap-1.5">
                {app.screens.map((_, i) => (
                  <span key={i} className={cn("h-1.5 rounded-full transition-all", i === tab ? "w-6 bg-brand-500" : "w-1.5 bg-brand-500/30")} />
                ))}
              </div>
            </Reveal>

            {/* Details */}
            <AnimatePresence mode="wait">
              <motion.div
                key={app.slug}
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                transition={{ duration: 0.3 }}
                className="rounded-2xl border border-token bg-surface p-7"
              >
                <div className="text-xs font-semibold uppercase tracking-wider text-brand-500">{app.industry}</div>
                <h3 className="mt-2 text-2xl font-bold">{app.name}</h3>
                <p className="mt-3 text-sm leading-relaxed text-secondary-token">{app.desc}</p>
                <div className="mt-5 text-xs font-semibold uppercase tracking-wider text-muted-token">Key features</div>
                <ul className="mt-3 space-y-2">
                  {app.features.map((f) => (
                    <li key={f} className="flex items-center gap-2 text-sm">
                      <Check className="h-4 w-4 text-brand-500" /> {f}
                    </li>
                  ))}
                </ul>
                <div className="mt-5 flex flex-wrap gap-2">
                  {app.platforms.map((p) => (
                    <span key={p} className="rounded-full border border-token bg-app px-3 py-1 text-xs font-medium text-secondary-token">
                      {p}
                    </span>
                  ))}
                </div>
                <Button
                  href={quoteHref("App Development", `I'd like an app like the "${app.name}" (${app.industry}) demo, customised for my business.`)}
                  className="mt-7 w-full"
                >
                  Get an app like this <ArrowRight className="h-4 w-4" />
                </Button>
              </motion.div>
            </AnimatePresence>
          </div>
        </Container>
      </Section>

      <Section id="custom-software" className="scroll-mt-20 bg-surface">
        <Container>
          <Reveal>
            <SectionHeading
              eyebrow="Custom software"
              title="Business software built around your process"
              subtitle="When off-the-shelf tools don't fit, we build exactly what you need — on the web, the desktop or both."
            />
          </Reveal>
          <div className="mt-12 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {customSoftware.map((s, i) => (
              <Reveal key={s.title} delay={i * 0.06}>
                <TiltCard className="h-full rounded-2xl">
                  <div className="ring-conic h-full rounded-2xl border border-token bg-app p-6">
                    <div className="grid h-11 w-11 place-items-center rounded-xl bg-gradient-to-br from-brand-600 to-cyan-500 text-white">
                      <s.icon className="h-5 w-5" />
                    </div>
                    <h3 className="mt-4 font-bold">{s.title}</h3>
                    <p className="mt-1.5 text-sm text-secondary-token">{s.desc}</p>
                  </div>
                </TiltCard>
              </Reveal>
            ))}
          </div>
        </Container>
      </Section>

      <Section>
        <Container>
          <Reveal>
            <SectionHeading eyebrow="What you get" title="Everything an app needs to succeed" />
          </Reveal>
          <div className="mt-12">
            <MiniFeatures items={capabilities} />
          </div>
        </Container>
      </Section>

      <QuoteBand
        title="Have an app idea?"
        sub="Share it with us — we'll turn it into screens, a plan and a quote, free of charge."
        interest="App Development"
      />
    </>
  );
}
