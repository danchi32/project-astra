"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowRight, Check, LayoutGrid, Plus, Server } from "lucide-react";
import { Container, Section, Reveal, SectionHeading, Button } from "@/components/ui";
import { Marquee } from "@/components/enhance";
import { hardwareBrands, hardwareCategories, hardwareServices, quoteHref } from "@/lib/services";
import { cn } from "@/lib/utils";
import { ServiceHero, MiniFeatures, QuoteBand, QuoteBar, useQuoteList } from "../shared";

export function HardwareContent() {
  const [cat, setCat] = useState("all");
  const quote = useQuoteList();
  const shown = hardwareCategories.filter((c) => cat === "all" || c.key === cat);

  return (
    <>
      <ServiceHero
        icon={Server}
        crumb="IT Hardware & Assets"
        badge="IT hardware & assets"
        title="Every IT asset your office needs, [[ready to work on day one]]"
        sub="Laptops, desktops, servers, firewalls, networking, printers, UPS and CCTV from leading brands — configured, tagged and delivered by our team."
      >
        <Button href="#catalogue">
          Browse the catalogue <ArrowRight className="h-4 w-4" />
        </Button>
        <Button href={quoteHref("IT Hardware", "I need a quote for IT hardware.")} variant="secondary">
          Request a bulk quote
        </Button>
      </ServiceHero>

      <section className="border-y border-token bg-surface/60 py-5">
        <Marquee duration={30}>
          {hardwareBrands.map((b) => (
            <span key={b} className="whitespace-nowrap text-base font-bold tracking-tight text-muted-token">
              {b}
            </span>
          ))}
        </Marquee>
      </section>

      <Section id="catalogue" className="scroll-mt-20">
        <Container>
          <Reveal>
            <SectionHeading
              eyebrow="Catalogue"
              title="What we supply"
              subtitle="Tap “Add” on anything you need and send one quote request for the whole list. Pricing depends on model and quantity, so every quote is tailored."
            />
          </Reveal>

          {/* Category chips */}
          <div className="sticky top-2 z-30 mt-10 -mx-2 overflow-x-auto px-2 pb-2 [scrollbar-width:none]">
            <div className="mx-auto flex w-max gap-2 rounded-2xl border border-token bg-surface/90 p-1.5 shadow-lg backdrop-blur">
              {[{ key: "all", title: "All", icon: LayoutGrid }, ...hardwareCategories].map((c) => (
                <button
                  key={c.key}
                  type="button"
                  onClick={() => setCat(c.key)}
                  className={cn(
                    "relative flex items-center gap-1.5 whitespace-nowrap rounded-xl px-3 py-2 text-xs font-medium transition-colors",
                    cat === c.key ? "text-white" : "text-secondary-token hover:text-primary-token",
                  )}
                >
                  {cat === c.key && (
                    <motion.span layoutId="hw-pill" className="absolute inset-0 rounded-xl bg-brand-600" transition={{ type: "spring", stiffness: 380, damping: 30 }} />
                  )}
                  <c.icon className="relative h-3.5 w-3.5" />
                  <span className="relative">{c.title}</span>
                </button>
              ))}
            </div>
          </div>

          <div className="mt-10 space-y-14">
            <AnimatePresence mode="popLayout">
              {shown.map((c) => (
                <motion.div
                  key={c.key}
                  layout
                  initial={{ opacity: 0, y: 24 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.35 }}
                >
                  <div className="flex items-center gap-4">
                    <span className="grid h-12 w-12 place-items-center rounded-xl bg-gradient-to-br from-brand-600 to-cyan-500 text-white shadow-lg shadow-brand-600/25">
                      <c.icon className="h-6 w-6" />
                    </span>
                    <div>
                      <h3 className="text-xl font-bold">{c.title}</h3>
                      <p className="text-sm text-secondary-token">{c.blurb}</p>
                    </div>
                  </div>
                  <div className="mt-6 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                    {c.items.map((it, i) => {
                      const label = `${c.title}: ${it.name}`;
                      const added = quote.has(label);
                      return (
                        <motion.div
                          key={it.name}
                          initial={{ opacity: 0, y: 16 }}
                          whileInView={{ opacity: 1, y: 0 }}
                          viewport={{ once: true }}
                          transition={{ delay: i * 0.06 }}
                          whileHover={{ y: -4 }}
                          className={cn(
                            "relative flex flex-col overflow-hidden rounded-2xl border bg-surface p-6 transition-colors",
                            added ? "border-brand-500/70 shadow-lg shadow-brand-600/10" : "border-token hover:border-brand-500/40",
                          )}
                        >
                          <c.icon className="pointer-events-none absolute -right-4 -top-4 h-24 w-24 text-brand-500/[0.07]" />
                          {it.tag && (
                            <span className="mb-3 w-max rounded-full bg-brand-500/10 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider text-brand-500">
                              {it.tag}
                            </span>
                          )}
                          <h4 className="font-bold">{it.name}</h4>
                          <p className="mt-2 text-sm font-medium text-primary-token">{it.brands}</p>
                          <p className="mt-2 flex-1 text-xs leading-relaxed text-secondary-token">{it.specs}</p>
                          <button
                            type="button"
                            onClick={() => quote.toggle(label)}
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
              ))}
            </AnimatePresence>
          </div>
        </Container>
      </Section>

      <Section className="bg-surface">
        <Container>
          <Reveal>
            <SectionHeading eyebrow="More than a box" title="Ready to use the moment it arrives" />
          </Reveal>
          <div className="mt-12">
            <MiniFeatures items={hardwareServices} />
          </div>
        </Container>
      </Section>

      <QuoteBand
        title="Equipping a new office or refreshing your fleet?"
        sub="Send us your list — we'll recommend the right models and send a consolidated quote."
        interest="IT Hardware"
      />
      <QuoteBar items={quote.items} interest="IT Hardware" onClear={quote.clear} />
    </>
  );
}
