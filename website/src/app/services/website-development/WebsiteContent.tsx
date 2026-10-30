"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  ArrowRight,
  Check,
  Eye,
  Globe,
  Gauge,
  Search,
  Smartphone,
  PenTool,
  ShieldCheck,
  BarChart3,
  MessageCircle,
} from "lucide-react";
import { Container, Section, Reveal, SectionHeading, Button } from "@/components/ui";
import { Template } from "@/components/templates";
import { siteTemplates, quoteHref, type SiteTemplate } from "@/lib/services";
import { cn } from "@/lib/utils";
import { ServiceHero, MiniFeatures, QuoteBand } from "../shared";

const DESKTOP_W = 1280;

const included = [
  { icon: Smartphone, title: "Mobile-first design", desc: "Looks and works great on every phone, tablet and screen." },
  { icon: Gauge, title: "Fast loading", desc: "Optimised pages that load in a blink and rank better." },
  { icon: Search, title: "SEO ready", desc: "Clean structure, meta tags, sitemap and Google setup." },
  { icon: PenTool, title: "Easy editing", desc: "Change text and images yourself — no developer needed." },
  { icon: MessageCircle, title: "Leads & WhatsApp", desc: "Contact forms, WhatsApp chat and call buttons built in." },
  { icon: BarChart3, title: "Analytics", desc: "Google Analytics and Search Console connected." },
  { icon: ShieldCheck, title: "SSL & security", desc: "HTTPS, backups and security updates included." },
  { icon: Globe, title: "Domain & hosting", desc: "We set up your domain, email and hosting." },
];

const filters = ["All", "E-commerce", "3D", "Motion", "Business", "Creative", "Hospitality", "Healthcare", "Education"];

/** A template drawn at desktop width and scaled into its card; scrolls through the page on hover. */
function TemplateThumb({ t }: { t: SiteTemplate }) {
  const frame = useRef<HTMLDivElement>(null);
  const page = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(0.25);
  const [travel, setTravel] = useState(0);

  useEffect(() => {
    const el = frame.current;
    if (!el) return;
    const measure = () => {
      const s = el.clientWidth / DESKTOP_W;
      setScale(s);
      const h = page.current?.scrollHeight ?? 0;
      setTravel(Math.max(0, h * s - el.clientHeight));
    };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  return (
    <div ref={frame} className="relative aspect-[16/11] overflow-hidden bg-white">
      <div
        ref={page}
        aria-hidden
        className="pointer-events-none absolute left-0 top-0 origin-top-left transition-transform duration-[4000ms] ease-in-out [transform:scale(var(--scale))] group-hover:[transform:translateY(var(--travel))_scale(var(--scale))]"
        style={
          {
            width: DESKTOP_W,
            "--scale": scale,
            "--travel": `-${travel}px`,
          } as React.CSSProperties
        }
      >
        <Template slug={t.slug} thumb />
      </div>
    </div>
  );
}

export function WebsiteContent() {
  const [filter, setFilter] = useState("All");
  const shown = siteTemplates.filter((t) => filter === "All" || t.tags.includes(filter));

  return (
    <>
      <ServiceHero
        icon={Globe}
        crumb="Website Development"
        badge="Website development"
        title="Websites that look amazing and [[bring in customers]]"
        sub="Pick a ready-made template to launch fast, or get a fully custom design. Every site is mobile-first, SEO-ready and easy for you to update."
      >
        <Button href="#templates">
          Browse templates <ArrowRight className="h-4 w-4" />
        </Button>
        <Button href={quoteHref("Website Development", "I'd like a custom website for my business.")} variant="secondary">
          Get a custom website
        </Button>
      </ServiceHero>

      <Section id="templates" className="scroll-mt-20">
        <Container>
          <Reveal>
            <SectionHeading
              eyebrow="Ready-made templates"
              title="Preview a template live"
              subtitle="Hover a card to scroll through the page, or open the full live preview. Every template is customised with your brand, content and colours."
            />
          </Reveal>

          <Reveal delay={0.05}>
            <div className="mt-10 flex flex-wrap justify-center gap-2">
              {filters.map((f) => (
                <button
                  key={f}
                  type="button"
                  onClick={() => setFilter(f)}
                  className={cn(
                    "relative rounded-full px-4 py-2 text-sm font-medium transition-colors",
                    filter === f ? "text-white" : "text-secondary-token hover:text-primary-token",
                  )}
                >
                  {filter === f && (
                    <motion.span
                      layoutId="tpl-pill"
                      className="absolute inset-0 rounded-full bg-brand-600 shadow-lg shadow-brand-600/30"
                      transition={{ type: "spring", stiffness: 380, damping: 30 }}
                    />
                  )}
                  <span className="relative">{f}</span>
                </button>
              ))}
            </div>
          </Reveal>

          <motion.div layout className="mt-10 grid gap-7 md:grid-cols-2">
            <AnimatePresence mode="popLayout">
              {shown.map((t, i) => (
                <motion.div
                  key={t.slug}
                  layout
                  initial={{ opacity: 0, y: 24, scale: 0.96 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.95 }}
                  transition={{ duration: 0.4, delay: i * 0.05 }}
                  className="group overflow-hidden rounded-2xl border border-token bg-surface shadow-sm transition-shadow hover:shadow-2xl hover:shadow-brand-600/10"
                >
                  <div className="flex items-center gap-1.5 border-b border-token bg-surface-2 px-4 py-2.5">
                    <span className="h-2.5 w-2.5 rounded-full bg-red-400/80" />
                    <span className="h-2.5 w-2.5 rounded-full bg-amber-400/80" />
                    <span className="h-2.5 w-2.5 rounded-full bg-emerald-400/80" />
                    <span className="ml-3 truncate text-[11px] text-muted-token">
                      www.{t.brand}.com
                    </span>
                  </div>
                  <Link href={`/services/website-development/templates/${t.slug}/`} className="block">
                    <TemplateThumb t={t} />
                  </Link>
                  <div className="p-6">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <h3 className="text-lg font-bold">{t.name}</h3>
                        <p className="text-sm text-brand-500">{t.industry}</p>
                      </div>
                      <div className="flex gap-1.5">
                        {t.swatches.map((c) => (
                          <span key={c} className="h-5 w-5 rounded-full border border-token" style={{ background: c }} />
                        ))}
                      </div>
                    </div>
                    <p className="mt-3 text-sm text-secondary-token">{t.desc}</p>
                    <ul className="mt-4 space-y-1.5">
                      {t.highlights.map((h) => (
                        <li key={h} className="flex items-center gap-2 text-xs text-secondary-token">
                          <Check className="h-3.5 w-3.5 text-brand-500" /> {h}
                        </li>
                      ))}
                    </ul>
                    <div className="mt-4 flex flex-wrap gap-2">
                      {t.tags.map((tag) => (
                        <span key={tag} className="rounded-md border border-token bg-app px-2 py-1 text-[11px] text-muted-token">
                          {tag}
                        </span>
                      ))}
                    </div>
                    <div className="mt-6 flex flex-wrap gap-3">
                      <Button href={`/services/website-development/templates/${t.slug}/`} className="px-4 py-2.5">
                        <Eye className="h-4 w-4" /> Live preview
                      </Button>
                      <Button
                        href={quoteHref("Website Development", `I'd like a website based on the "${t.name}" (${t.industry}) template.`)}
                        variant="secondary"
                        className="px-4 py-2.5"
                      >
                        Use this template
                      </Button>
                    </div>
                  </div>
                </motion.div>
              ))}
            </AnimatePresence>
          </motion.div>
        </Container>
      </Section>

      <Section className="bg-surface">
        <Container>
          <Reveal>
            <SectionHeading eyebrow="Included in every website" title="Everything you need to go live" />
          </Reveal>
          <div className="mt-12">
            <MiniFeatures items={included} />
          </div>
          <Reveal delay={0.2}>
            <div className="mx-auto mt-14 max-w-3xl rounded-2xl border border-token bg-app p-8">
              <h3 className="text-xl font-bold">Need something completely custom?</h3>
              <p className="mt-2 text-sm text-secondary-token">
                Beyond templates we design and build fully custom websites, e-commerce stores with payment gateways,
                booking systems, multilingual sites and web portals — with motion and 3D like the site you&apos;re on.
              </p>
              <ul className="mt-5 grid gap-2 sm:grid-cols-2">
                {["E-commerce with UPI & cards", "Booking & appointment systems", "Customer / dealer portals", "Hindi & multilingual sites", "Blog & content hubs", "Animations & 3D"].map((x) => (
                  <li key={x} className="flex items-center gap-2 text-sm">
                    <Check className="h-4 w-4 text-brand-500" /> {x}
                  </li>
                ))}
              </ul>
            </div>
          </Reveal>
        </Container>
      </Section>

      <QuoteBand
        title="Let's build your website"
        sub="Pick a template or describe your idea — we'll send a proposal with timeline and cost."
        interest="Website Development"
      />
    </>
  );
}
