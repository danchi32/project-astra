"use client";

import type { LucideIcon } from "lucide-react";
import { ArrowRight, ChevronRight } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Container, Section, Reveal, Badge, Button } from "@/components/ui";
import { AnimatedBackground } from "@/components/AnimatedBackground";
import { Rich } from "@/lib/content";
import { quoteHref } from "@/lib/services";

/** Hero shared by the /services pages, with a breadcrumb back to the hub. */
export function ServiceHero({
  icon: Icon,
  badge,
  title,
  sub,
  crumb,
  children,
}: {
  icon: LucideIcon;
  badge: string;
  title: string;
  sub: string;
  crumb?: string;
  children?: React.ReactNode;
}) {
  return (
    <section className="aurora grain relative -mt-16 overflow-hidden pt-32 pb-16 sm:pt-40 sm:pb-20">
      <AnimatedBackground />
      <Container className="relative z-10 text-center">
        {crumb && (
          <Reveal>
            <nav className="mb-5 flex items-center justify-center gap-1 text-xs text-muted-token">
              <Link href="/services" className="hover:text-brand-500">
                Services
              </Link>
              <ChevronRight className="h-3 w-3" />
              <span className="text-secondary-token">{crumb}</span>
            </nav>
          </Reveal>
        )}
        <Reveal>
          <Badge>
            <Icon className="h-3.5 w-3.5 text-brand-500" /> {badge}
          </Badge>
        </Reveal>
        <Reveal delay={0.05}>
          <h1 className="mx-auto mt-5 max-w-4xl text-4xl font-extrabold leading-tight tracking-tight sm:text-6xl">
            <Rich text={title} />
          </h1>
        </Reveal>
        <Reveal delay={0.1}>
          <p className="mx-auto mt-6 max-w-2xl text-lg leading-relaxed text-secondary-token">{sub}</p>
        </Reveal>
        {children && (
          <Reveal delay={0.15}>
            <div className="mt-8 flex flex-wrap justify-center gap-3">{children}</div>
          </Reveal>
        )}
      </Container>
    </section>
  );
}

/** Small icon + title + text cards, e.g. "what's included" rows. */
export function MiniFeatures({ items }: { items: { icon: LucideIcon; title: string; desc: string }[] }) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {items.map((f, i) => (
        <Reveal key={f.title} delay={i * 0.08}>
          <motion.div
            whileHover={{ y: -4 }}
            className="h-full rounded-2xl border border-token bg-surface p-5 transition-colors hover:border-brand-500/40"
          >
            <f.icon className="h-6 w-6 text-brand-500" />
            <h3 className="mt-3 text-sm font-bold">{f.title}</h3>
            <p className="mt-1 text-xs leading-relaxed text-secondary-token">{f.desc}</p>
          </motion.div>
        </Reveal>
      ))}
    </div>
  );
}

/** Items a visitor has picked from a catalogue, to send as one quote request. */
export function useQuoteList() {
  const [items, setItems] = useState<string[]>([]);
  const toggle = (name: string) =>
    setItems((xs) => (xs.includes(name) ? xs.filter((x) => x !== name) : [...xs, name]));
  return { items, toggle, has: (name: string) => items.includes(name), clear: () => setItems([]) };
}

/** Floating bar for the quote list; sends everything picked to the contact form. */
export function QuoteBar({ items, interest, onClear }: { items: string[]; interest: string; onClear: () => void }) {
  return (
    <AnimatePresence>
      {items.length > 0 && (
        <motion.div
          initial={{ y: 120, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: 120, opacity: 0 }}
          transition={{ type: "spring", stiffness: 300, damping: 28 }}
          className="fixed inset-x-0 bottom-24 z-40 mx-auto flex w-[min(92vw,640px)] sm:bottom-6 items-center gap-3 rounded-2xl border border-token bg-surface/95 p-3 pl-5 shadow-2xl shadow-brand-600/20 backdrop-blur"
        >
          <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-brand-600 text-sm font-bold text-white">
            {items.length}
          </span>
          <span className="min-w-0 flex-1 truncate text-sm text-secondary-token">{items.join(", ")}</span>
          <button type="button" onClick={onClear} className="text-xs text-muted-token hover:text-primary-token">
            Clear
          </button>
          <Link
            href={quoteHref(interest, `Please send a quote for:\n${items.map((x) => `- ${x}`).join("\n")}\n\nQuantity / requirements: `)}
            className="inline-flex shrink-0 items-center gap-1.5 rounded-xl bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-brand-500"
          >
            Request quote <ArrowRight className="h-4 w-4" />
          </Link>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

/** Closing call to action that opens the contact form pre-filled for this service. */
export function QuoteBand({ title, sub, interest, button = "Get a free quote" }: { title: string; sub: string; interest: string; button?: string }) {
  return (
    <Section className="pb-28">
      <Container>
        <Reveal>
          <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-brand-700 via-brand-600 to-cyan-500 px-8 py-14 text-center text-white">
            <div className="grid-bg pointer-events-none absolute inset-0 opacity-20" />
            <motion.div
              aria-hidden
              className="pointer-events-none absolute -right-20 -top-20 h-72 w-72 rounded-full bg-white/20 blur-3xl"
              animate={{ scale: [1, 1.2, 1], opacity: [0.5, 0.8, 0.5] }}
              transition={{ duration: 6, repeat: Infinity }}
            />
            <h2 className="relative text-2xl font-bold sm:text-4xl">{title}</h2>
            <p className="relative mx-auto mt-3 max-w-xl text-white/85">{sub}</p>
            <div className="relative mt-7 flex flex-wrap justify-center gap-3">
              <Link
                href={quoteHref(interest)}
                className="inline-flex items-center gap-2 rounded-xl bg-white px-5 py-3 text-sm font-semibold text-brand-700 shadow-lg transition hover:-translate-y-0.5"
              >
                {button} <ArrowRight className="h-4 w-4" />
              </Link>
              <Button href="/services" variant="secondary" className="border-white/40 bg-white/10 text-white hover:border-white">
                All services
              </Button>
            </div>
          </div>
        </Reveal>
      </Container>
    </Section>
  );
}
