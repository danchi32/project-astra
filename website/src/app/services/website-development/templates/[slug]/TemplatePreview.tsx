"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { ArrowLeft, ArrowRight, ChevronLeft, ChevronRight, Monitor, Smartphone } from "lucide-react";
import { Template } from "@/components/templates";
import { getTemplate, quoteHref, siteTemplates } from "@/lib/services";
import { cn } from "@/lib/utils";

export function TemplatePreview({ slug }: { slug: string }) {
  const t = getTemplate(slug)!;
  const [device, setDevice] = useState<"desktop" | "mobile">("desktop");
  const [narrow, setNarrow] = useState(false);

  // On a real phone the desktop view is the phone view; the toggle only matters on wide screens.
  useEffect(() => {
    const mq = window.matchMedia("(max-width: 767px)");
    const set = () => setNarrow(mq.matches);
    set();
    mq.addEventListener("change", set);
    return () => mq.removeEventListener("change", set);
  }, []);

  const i = siteTemplates.findIndex((x) => x.slug === slug);
  const prev = siteTemplates[(i - 1 + siteTemplates.length) % siteTemplates.length];
  const next = siteTemplates[(i + 1) % siteTemplates.length];
  const url = `www.${t.brand}.com`;

  return (
    <div className="pb-20">
      {/* Toolbar */}
      <div className="sticky top-0 z-40 border-y border-token bg-surface/95 backdrop-blur">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-5 py-3">
          <div className="flex items-center gap-3">
            <Link
              href="/services/website-development/#templates"
              className="grid h-9 w-9 place-items-center rounded-lg border border-token hover:border-brand-500/50"
              aria-label="Back to templates"
            >
              <ArrowLeft className="h-4 w-4" />
            </Link>
            <div>
              <div className="text-sm font-bold">
                {t.name} <span className="font-normal text-muted-token">· template preview</span>
              </div>
              <div className="text-xs text-brand-500">{t.industry}</div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {!narrow && (
              <div className="flex rounded-lg border border-token bg-app p-1">
                {(["desktop", "mobile"] as const).map((d) => (
                  <button
                    key={d}
                    type="button"
                    onClick={() => setDevice(d)}
                    aria-label={`${d} view`}
                    className={cn(
                      "relative grid h-7 w-9 place-items-center rounded-md transition-colors",
                      device === d ? "text-white" : "text-muted-token hover:text-primary-token",
                    )}
                  >
                    {device === d && <motion.span layoutId="dev-pill" className="absolute inset-0 rounded-md bg-brand-600" />}
                    {d === "desktop" ? <Monitor className="relative h-4 w-4" /> : <Smartphone className="relative h-4 w-4" />}
                  </button>
                ))}
              </div>
            )}
            <Link
              href={`/services/website-development/templates/${prev.slug}/`}
              aria-label={`Previous template: ${prev.name}`}
              className="grid h-9 w-9 place-items-center rounded-lg border border-token hover:border-brand-500/50"
            >
              <ChevronLeft className="h-4 w-4" />
            </Link>
            <Link
              href={`/services/website-development/templates/${next.slug}/`}
              aria-label={`Next template: ${next.name}`}
              className="grid h-9 w-9 place-items-center rounded-lg border border-token hover:border-brand-500/50"
            >
              <ChevronRight className="h-4 w-4" />
            </Link>
            <Link
              href={quoteHref("Website Development", `I'd like a website based on the "${t.name}" (${t.industry}) template.`)}
              className="inline-flex items-center gap-1.5 rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white shadow-lg shadow-brand-600/25 hover:bg-brand-500"
            >
              Use this template <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
        </div>
      </div>

      <p className="mx-auto mt-5 max-w-3xl px-5 text-center text-xs text-muted-token">
        Sample content for demonstration — names, prices and reviews are placeholders. Your site gets your own brand, text and photos.
      </p>

      <motion.div
        key={device}
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="mt-6 px-3 sm:px-6"
      >
        {device === "mobile" && !narrow ? (
          <div className="mx-auto w-[390px] overflow-hidden rounded-[3rem] border-[10px] border-neutral-900 bg-neutral-900 shadow-2xl [transform:translateZ(0)]">
            <div className="mx-auto mb-2 mt-1 h-5 w-28 rounded-full bg-black" />
            <div className="h-[760px] overflow-y-auto overflow-x-hidden rounded-[2.2rem]">
              <Template slug={t.slug} compact />
            </div>
          </div>
        ) : (
          <div className="mx-auto max-w-7xl overflow-hidden rounded-2xl border border-token shadow-2xl shadow-brand-600/10">
            <div className="flex items-center gap-1.5 border-b border-token bg-surface-2 px-4 py-2.5">
              <span className="h-2.5 w-2.5 rounded-full bg-red-400/80" />
              <span className="h-2.5 w-2.5 rounded-full bg-amber-400/80" />
              <span className="h-2.5 w-2.5 rounded-full bg-emerald-400/80" />
              <span className="ml-3 flex-1 truncate rounded-md bg-app px-3 py-1 text-[11px] text-muted-token">https://{url}</span>
            </div>
            <Template slug={t.slug} compact={narrow} />
          </div>
        )}
      </motion.div>
    </div>
  );
}
