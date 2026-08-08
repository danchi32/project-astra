import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { Container, Section, Badge, SectionHeading } from "@/components/ui";
import { site } from "@/lib/site";
import { comparisons } from "@/lib/comparisons";

export const metadata: Metadata = {
  title: "Compare Astra — AI IT Automation vs RMM Tools",
  description:
    "See how Astra, the AI System Administrator, compares to popular IT automation and RMM tools like NinjaOne and Atera. Honest, side-by-side breakdowns.",
  alternates: { canonical: "/compare/" },
};

export default function CompareIndexPage() {
  return (
    <Section className="pt-12 sm:pt-16">
      <Container>
        <div className="mx-auto max-w-2xl text-center">
          <Badge>Compare</Badge>
          <SectionHeading
            title={`How ${site.product} compares`}
            subtitle="Honest, side-by-side breakdowns of Astra against popular IT automation and RMM tools — including where each one is the better fit."
          />
        </div>

        <div className="mx-auto mt-14 grid max-w-4xl gap-5 sm:grid-cols-2">
          {comparisons.map((c) => (
            <Link
              key={c.slug}
              href={`/compare/${c.slug}/`}
              className="group flex flex-col rounded-2xl border border-token bg-surface p-6 transition-all hover:-translate-y-0.5 hover:border-brand-500/50"
            >
              <h2 className="text-lg font-bold">{c.h1}</h2>
              <p className="mt-2 flex-1 text-sm leading-relaxed text-secondary-token">
                {c.intro}
              </p>
              <span className="mt-4 inline-flex items-center gap-1.5 text-sm font-semibold text-brand-500">
                See the comparison
                <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
              </span>
            </Link>
          ))}
        </div>
      </Container>
    </Section>
  );
}
