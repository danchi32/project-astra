"use client";

import Link from "next/link";
import { ArrowRight, Check, Minus, ShieldCheck, Sparkles } from "lucide-react";
import {
  Container,
  Section,
  Reveal,
  Button,
  Badge,
  SectionHeading,
} from "@/components/ui";
import { site, bookDemo } from "@/lib/site";
import type { Comparison } from "@/lib/comparisons";
import { compareDisclaimer } from "@/lib/comparisons";

function EdgeDot({ edge }: { edge?: Comparison["rows"][number]["edge"] }) {
  if (edge === "astra")
    return <Check className="h-4 w-4 shrink-0 text-brand-500" />;
  return <Minus className="h-4 w-4 shrink-0 text-muted-token" />;
}

export function CompareContent({ data }: { data: Comparison }) {
  return (
    <>
      {/* Hero */}
      <Section className="aurora grain relative -mt-16 pb-10 pt-28 sm:pt-36">
        <Container>
          <Reveal className="mx-auto max-w-3xl text-center">
            <Badge>
              <Sparkles className="h-3.5 w-3.5 text-brand-500" /> Comparison
            </Badge>
            <h1 className="mt-5 text-4xl font-bold tracking-tight sm:text-5xl">
              {data.h1}
            </h1>
            <p className="mx-auto mt-5 max-w-2xl text-base leading-relaxed text-secondary-token sm:text-lg">
              {data.intro}
            </p>
            <div className="mt-8 flex flex-wrap justify-center gap-3">
              <Button href={bookDemo.href} external={bookDemo.external}>
                Book a demo <ArrowRight className="h-4 w-4" />
              </Button>
              <Button href="/astra" variant="secondary">
                Explore {site.product}
              </Button>
            </div>
          </Reveal>
        </Container>
      </Section>

      {/* Comparison table */}
      <Section className="py-12">
        <Container>
          <Reveal>
            <div className="overflow-x-auto rounded-2xl border border-token bg-surface">
              <table className="w-full min-w-[640px] border-collapse text-left text-sm">
                <thead>
                  <tr className="border-b border-token">
                    <th className="p-4 font-semibold text-secondary-token">
                      Feature
                    </th>
                    <th className="p-4 font-bold text-brand-500">
                      {site.product}
                    </th>
                    <th className="p-4 font-semibold text-secondary-token">
                      {data.competitor}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {data.rows.map((row) => (
                    <tr
                      key={row.feature}
                      className="border-b border-token last:border-0"
                    >
                      <td className="p-4 font-medium">{row.feature}</td>
                      <td className="bg-brand-500/[0.06] p-4">
                        <span className="flex items-start gap-2">
                          <EdgeDot edge={row.edge} />
                          <span>{row.astra}</span>
                        </span>
                      </td>
                      <td className="p-4 text-secondary-token">{row.them}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="mt-4 text-xs leading-relaxed text-muted-token">
              {compareDisclaimer}
            </p>
          </Reveal>
        </Container>
      </Section>

      {/* What is <competitor> */}
      <Section className="py-12">
        <Container>
          <Reveal className="mx-auto max-w-3xl">
            <h2 className="text-2xl font-bold tracking-tight sm:text-3xl">
              What is {data.competitor}?
            </h2>
            <p className="mt-4 text-base leading-relaxed text-secondary-token">
              {data.competitorSummary}
            </p>
          </Reveal>
        </Container>
      </Section>

      {/* Why ASTRA */}
      <Section className="py-12">
        <Container>
          <SectionHeading
            eyebrow={`Why teams choose ${site.product}`}
            title={`Where ${site.product} pulls ahead`}
          />
          <div className="mx-auto mt-12 grid max-w-4xl gap-5 sm:grid-cols-2">
            {data.whyAstra.map((point, i) => (
              <Reveal key={point} delay={i * 0.08}>
                <div className="flex h-full gap-3 rounded-2xl border border-token bg-surface p-5">
                  <ShieldCheck className="h-5 w-5 shrink-0 text-brand-500" />
                  <p className="text-sm leading-relaxed text-secondary-token">
                    {point}
                  </p>
                </div>
              </Reveal>
            ))}
          </div>
        </Container>
      </Section>

      {/* When competitor is the better fit (honest) */}
      <Section className="py-12">
        <Container>
          <Reveal className="mx-auto max-w-3xl rounded-2xl border border-token bg-surface p-7">
            <h2 className="text-xl font-bold tracking-tight sm:text-2xl">
              When {data.competitor} may be the better fit
            </h2>
            <ul className="mt-5 space-y-3">
              {data.whenThem.map((point) => (
                <li key={point} className="flex items-start gap-3">
                  <Check className="mt-0.5 h-4 w-4 shrink-0 text-secondary-token" />
                  <span className="text-sm leading-relaxed text-secondary-token">
                    {point}
                  </span>
                </li>
              ))}
            </ul>
          </Reveal>
        </Container>
      </Section>

      {/* FAQ */}
      <Section className="py-12">
        <Container>
          <SectionHeading eyebrow="FAQ" title="Common questions" />
          <div className="mx-auto mt-10 max-w-3xl divide-y divide-token">
            {data.faqs.map((faq) => (
              <div key={faq.q} className="py-5">
                <h3 className="text-base font-semibold">{faq.q}</h3>
                <p className="mt-2 text-sm leading-relaxed text-secondary-token">
                  {faq.a}
                </p>
              </div>
            ))}
          </div>
        </Container>
      </Section>

      {/* Final CTA */}
      <Section className="py-16">
        <Container>
          <Reveal className="mx-auto max-w-3xl rounded-3xl border border-token bg-brand-600/[0.08] p-10 text-center">
            <h2 className="text-2xl font-bold tracking-tight sm:text-3xl">
              See {site.product} on your own fleet
            </h2>
            <p className="mx-auto mt-3 max-w-xl text-secondary-token">
              Put your IT on autopilot with evidence-based, human-approved
              self-healing. Book a live demo and see it heal a real issue.
            </p>
            <div className="mt-7 flex flex-wrap justify-center gap-3">
              <Button href={bookDemo.href} external={bookDemo.external}>
                Book a demo <ArrowRight className="h-4 w-4" />
              </Button>
              <Button href="/pricing" variant="secondary">
                View pricing
              </Button>
            </div>
          </Reveal>
        </Container>
      </Section>
    </>
  );
}
