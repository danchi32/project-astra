"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { ArrowRight, Check, Layers, Search, PenTool, Hammer, LifeBuoy } from "lucide-react";
import { Container, Section, Reveal, SectionHeading, Button } from "@/components/ui";
import { TiltCard, Marquee } from "@/components/enhance";
import { serviceCategories, siteTemplates, hardwareBrands } from "@/lib/services";
import { ServiceHero, MiniFeatures, QuoteBand } from "./shared";

const steps = [
  { icon: Search, title: "Tell us what you need", desc: "A quick call or message — website, app, hardware or licenses." },
  { icon: PenTool, title: "Get a clear proposal", desc: "Scope, timeline and a transparent quote, usually within a day." },
  { icon: Hammer, title: "We deliver", desc: "Built, configured and installed by our own team." },
  { icon: LifeBuoy, title: "Ongoing support", desc: "Maintenance, renewals and a helpdesk that picks up." },
];

export function ServicesContent() {
  return (
    <>
      <ServiceHero
        icon={Layers}
        badge="Our services"
        title="Everything your business needs from IT — [[under one roof]]"
        sub="Websites, apps, custom software, laptops, servers, firewalls and Microsoft licenses — designed, supplied and supported by one accountable team."
      >
        <Button href="#all-services">
          Explore services <ArrowRight className="h-4 w-4" />
        </Button>
        <Button href="/contact" variant="secondary">
          Talk to us
        </Button>
      </ServiceHero>

      <section className="border-y border-token bg-surface/60 py-5">
        <Marquee duration={36}>
          {[...serviceCategories.map((s) => s.title), ...siteTemplates.map((t) => `${t.industry} websites`)].map((label) => (
            <span key={label} className="flex items-center gap-2 whitespace-nowrap text-sm font-medium text-muted-token">
              <span className="h-1.5 w-1.5 rounded-full bg-brand-500" />
              {label}
            </span>
          ))}
        </Marquee>
      </section>

      <Section id="all-services" className="scroll-mt-20">
        <Container>
          <Reveal>
            <SectionHeading
              eyebrow="What we do"
              title="Pick a service to explore"
              subtitle="Each one has live examples — website templates, app demos, a hardware catalogue and a full license list."
            />
          </Reveal>
          <div className="mt-14 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {serviceCategories.map((s, i) => (
              <Reveal key={s.href} delay={i * 0.06}>
                <Link href={s.href} className="block h-full">
                  <TiltCard className="h-full rounded-2xl">
                    <div className="ring-conic relative flex h-full flex-col overflow-hidden rounded-2xl border border-token bg-surface p-7 transition-shadow group-hover:shadow-xl group-hover:shadow-brand-600/10">
                      <div className="pointer-events-none absolute -right-10 -top-10 h-32 w-32 rounded-full bg-brand-500/10 blur-2xl transition-transform duration-500 group-hover:scale-150" />
                      <div className="grid h-12 w-12 place-items-center rounded-xl bg-gradient-to-br from-brand-600 to-cyan-500 text-white shadow-lg shadow-brand-600/25 transition-transform duration-300 group-hover:-rotate-6 group-hover:scale-110">
                        <s.icon className="h-6 w-6" />
                      </div>
                      <h3 className="mt-5 text-lg font-bold">{s.title}</h3>
                      <p className="mt-2 flex-1 text-sm leading-relaxed text-secondary-token">{s.desc}</p>
                      <ul className="mt-5 space-y-1.5">
                        {s.points.map((p) => (
                          <li key={p} className="flex items-center gap-2 text-xs text-secondary-token">
                            <Check className="h-3.5 w-3.5 text-brand-500" /> {p}
                          </li>
                        ))}
                      </ul>
                      <span className="mt-6 inline-flex items-center gap-1.5 text-sm font-semibold text-brand-500">
                        Explore
                        <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
                      </span>
                    </div>
                  </TiltCard>
                </Link>
              </Reveal>
            ))}
          </div>
        </Container>
      </Section>

      <Section className="bg-surface">
        <Container>
          <Reveal>
            <SectionHeading eyebrow="How it works" title="Simple from first call to ongoing support" />
          </Reveal>
          <div className="mt-12">
            <MiniFeatures items={steps} />
          </div>
          <Reveal delay={0.2}>
            <div className="mt-14 text-center text-xs font-semibold uppercase tracking-wider text-muted-token">
              Hardware brands we supply
            </div>
            <div className="mt-5 flex flex-wrap justify-center gap-2">
              {hardwareBrands.map((b, i) => (
                <motion.span
                  key={b}
                  initial={{ opacity: 0, y: 8 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: i * 0.03 }}
                  className="rounded-full border border-token bg-app px-3.5 py-1.5 text-xs font-semibold text-secondary-token"
                >
                  {b}
                </motion.span>
              ))}
            </div>
          </Reveal>
        </Container>
      </Section>

      <QuoteBand
        title="Not sure where to start?"
        sub="Tell us what you're trying to do and we'll recommend the right mix — no obligation."
        interest="Something else"
        button="Get a recommendation"
      />
    </>
  );
}
