"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowRight, Check, KeyRound, Plus, ShieldCheck } from "lucide-react";
import { Container, Section, Reveal, SectionHeading, Button } from "@/components/ui";
import { licenseGroups, licenseServices, otherSoftware, quoteHref } from "@/lib/services";
import { cn } from "@/lib/utils";
import { ServiceHero, MiniFeatures, QuoteBand, QuoteBar, useQuoteList } from "../shared";

const typeTone = {
  Subscription: "bg-blue-500/10 text-blue-500",
  Perpetual: "bg-emerald-500/10 text-emerald-500",
  "Add-on": "bg-fuchsia-500/10 text-fuchsia-500",
};

export function LicensesContent() {
  const [group, setGroup] = useState(licenseGroups[0].key);
  const quote = useQuoteList();
  const g = licenseGroups.find((x) => x.key === group)!;

  return (
    <>
      <ServiceHero
        icon={KeyRound}
        crumb="Software & Licenses"
        badge="Software & licenses"
        title="Genuine Microsoft licenses, [[set up the right way]]"
        sub="Microsoft 365, Windows 11 Pro, Windows Server, SQL Server, Office and more — the right plan for every user, deployed, secured and renewed on time."
      >
        <Button href="#licenses">
          View licenses <ArrowRight className="h-4 w-4" />
        </Button>
        <Button href={quoteHref("Software Licenses", "I need help choosing the right Microsoft licenses.")} variant="secondary">
          Help me choose
        </Button>
      </ServiceHero>

      <Section id="licenses" className="scroll-mt-20">
        <Container>
          <Reveal>
            <SectionHeading
              eyebrow="License catalogue"
              title="Pick a product family"
              subtitle="Add what you need to your quote list. Pricing depends on the plan, user count and billing term, so we send an exact quote."
            />
          </Reveal>

          <div className="mt-10 grid gap-8 lg:grid-cols-[260px_1fr]">
            {/* Group picker */}
            <div className="flex gap-2 overflow-x-auto pb-2 lg:flex-col lg:overflow-visible">
              {licenseGroups.map((x) => (
                <button
                  key={x.key}
                  type="button"
                  onClick={() => setGroup(x.key)}
                  className={cn(
                    "relative flex shrink-0 items-center gap-3 rounded-xl px-4 py-3 text-left text-sm font-semibold transition-colors",
                    group === x.key ? "text-white" : "text-secondary-token hover:bg-surface hover:text-primary-token",
                  )}
                >
                  {group === x.key && (
                    <motion.span layoutId="lic-pill" className="absolute inset-0 rounded-xl bg-gradient-to-r from-brand-600 to-cyan-500 shadow-lg shadow-brand-600/25" transition={{ type: "spring", stiffness: 380, damping: 30 }} />
                  )}
                  <x.icon className="relative h-4 w-4" />
                  <span className="relative whitespace-nowrap">{x.title}</span>
                  <span className={cn("relative ml-auto rounded-full px-2 text-[10px]", group === x.key ? "bg-white/20" : "bg-surface-2")}>
                    {x.items.length}
                  </span>
                </button>
              ))}
            </div>

            <AnimatePresence mode="wait">
              <motion.div
                key={g.key}
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                transition={{ duration: 0.3 }}
              >
                <p className="text-secondary-token">{g.blurb}</p>
                <div className="mt-6 grid gap-4 md:grid-cols-2">
                  {g.items.map((it, i) => {
                    const added = quote.has(it.name);
                    return (
                      <motion.div
                        key={it.name}
                        initial={{ opacity: 0, y: 14 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: i * 0.05 }}
                        whileHover={{ y: -4 }}
                        className={cn(
                          "ring-conic flex flex-col rounded-2xl border bg-surface p-6 transition-colors",
                          added ? "border-brand-500/70 shadow-lg shadow-brand-600/10" : "border-token",
                        )}
                      >
                        <div className="flex flex-wrap items-center gap-2">
                          <span className={cn("rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider", typeTone[it.type])}>
                            {it.type}
                          </span>
                          {it.tag && (
                            <span className="rounded-full bg-amber-500/10 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider text-amber-500">
                              {it.tag}
                            </span>
                          )}
                        </div>
                        <h3 className="mt-3 text-lg font-bold">{it.name}</h3>
                        <p className="mt-1 text-sm text-secondary-token">{it.for}</p>
                        <ul className="mt-4 flex-1 space-y-1.5">
                          {it.includes.map((x) => (
                            <li key={x} className="flex items-start gap-2 text-xs text-secondary-token">
                              <Check className="mt-0.5 h-3.5 w-3.5 shrink-0 text-brand-500" /> {x}
                            </li>
                          ))}
                        </ul>
                        <button
                          type="button"
                          onClick={() => quote.toggle(it.name)}
                          className={cn(
                            "mt-5 inline-flex items-center justify-center gap-1.5 rounded-xl px-4 py-2.5 text-sm font-semibold transition-all",
                            added ? "bg-brand-600 text-white" : "border border-token bg-app hover:border-brand-500/50",
                          )}
                        >
                          {added ? <Check className="h-4 w-4" /> : <Plus className="h-4 w-4" />}
                          {added ? "Added to quote" : "Add to quote"}
                        </button>
                      </motion.div>
                    );
                  })}
                </div>
              </motion.div>
            </AnimatePresence>
          </div>

          <Reveal delay={0.1}>
            <div className="mt-14 rounded-2xl border border-token bg-surface p-7">
              <h3 className="font-bold">Other business software</h3>
              <p className="mt-1 text-sm text-secondary-token">We also supply and deploy licenses beyond Microsoft — ask for anything not listed.</p>
              <div className="mt-5 flex flex-wrap gap-2">
                {otherSoftware.map((s) => {
                  const added = quote.has(s);
                  return (
                    <button
                      key={s}
                      type="button"
                      onClick={() => quote.toggle(s)}
                      className={cn(
                        "inline-flex items-center gap-1.5 rounded-full border px-3.5 py-1.5 text-xs font-medium transition-colors",
                        added ? "border-brand-500 bg-brand-600 text-white" : "border-token bg-app text-secondary-token hover:border-brand-500/50",
                      )}
                    >
                      {added ? <Check className="h-3 w-3" /> : <Plus className="h-3 w-3" />} {s}
                    </button>
                  );
                })}
              </div>
            </div>
          </Reveal>
        </Container>
      </Section>

      <Section className="bg-surface">
        <Container>
          <Reveal>
            <SectionHeading eyebrow="Not just a license key" title="We set it up and keep it running" />
          </Reveal>
          <div className="mt-12">
            <MiniFeatures items={licenseServices} />
          </div>
          <Reveal delay={0.2}>
            <p className="mx-auto mt-10 flex max-w-3xl items-start justify-center gap-2 text-center text-xs text-muted-token">
              <ShieldCheck className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              Microsoft, Microsoft 365, Windows, Office and other product names are trademarks of their respective owners and
              are used here only to identify the products we supply.
            </p>
          </Reveal>
        </Container>
      </Section>

      <QuoteBand
        title="Licensing a team or renewing soon?"
        sub="Tell us your user count and what you use today — we'll recommend the right plans and send a quote."
        interest="Software Licenses"
      />
      <QuoteBar items={quote.items} interest="Software Licenses" onClear={quote.clear} />
    </>
  );
}
