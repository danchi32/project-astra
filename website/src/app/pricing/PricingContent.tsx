"use client";

import { HelpCircle } from "lucide-react";
import { Container, Section, Reveal, Badge, SectionHeading } from "@/components/ui";
import { AnimatedBackground } from "@/components/AnimatedBackground";
import { PricingPlans } from "@/components/PricingPlans";
import { useContent, Rich } from "@/lib/content";

type Faq = { q: string; a: string };
const faqDefaults: Faq[] = [
  {
    q: "How is Astra priced?",
    a: "Astra is priced per user. Current plans start at $5.99/user per month for teams up to 50 users and $4.49/user per month for larger teams, with discounted annual billing. For 500+ users or custom requirements, contact sales.",
  },
  {
    q: "Is there a free trial?",
    a: "Yes — start with a free trial, no credit card required to explore the platform.",
  },
  {
    q: "Can I change plans later?",
    a: "Absolutely. Upgrade or downgrade at any time; billing adjusts on your next cycle based on your active users.",
  },
  {
    q: "Do you supply the hardware too?",
    a: "Yes — Technomate is also a laptop and hardware supplier. Bundle devices with Astra for a fully managed rollout.",
  },
];

export function PricingContent() {
  const { c, list } = useContent();
  const faqs = list<Faq>("pricing.faqs", faqDefaults);

  return (
    <>
      <section className="relative overflow-hidden pt-32 pb-10 sm:pt-40">
        <AnimatedBackground />
        <Container>
          <div className="mx-auto max-w-2xl text-center">
            <Reveal>
              <Badge className="mx-auto">{c("pricing.badge", "Pricing")}</Badge>
            </Reveal>
            <Reveal delay={0.05}>
              <h1 className="mt-5 text-4xl font-extrabold tracking-tight sm:text-5xl">
                <Rich text={c("pricing.title", "Simple pricing that [[scales with you]]")} />
              </h1>
            </Reveal>
            <Reveal delay={0.1}>
              <p className="mt-5 text-lg text-secondary-token">
                {c(
                  "pricing.subtitle",
                  "Pay per user. Start small, grow to thousands — Astra scales with your team.",
                )}
              </p>
            </Reveal>
          </div>
        </Container>
      </section>

      <Section className="pt-6">
        <Container>
          <Reveal>
            <PricingPlans />
          </Reveal>
        </Container>
      </Section>

      {/* FAQ */}
      <Section className="bg-surface">
        <Container>
          <Reveal>
            <SectionHeading
              eyebrow={c("pricing.faqHead.eyebrow", "FAQ")}
              title={c("pricing.faqHead.title", "Questions, answered")}
            />
          </Reveal>
          <div className="mx-auto mt-12 max-w-3xl space-y-4">
            {faqs.map((f, i) => (
              <Reveal key={f.q} delay={i * 0.08}>
                <div className="rounded-2xl border border-token bg-app p-6">
                  <h3 className="flex items-center gap-2 text-base font-semibold">
                    <HelpCircle className="h-5 w-5 text-brand-500" />
                    {f.q}
                  </h3>
                  <p className="mt-2 pl-7 text-sm leading-relaxed text-secondary-token">
                    {f.a}
                  </p>
                </div>
              </Reveal>
            ))}
          </div>
        </Container>
      </Section>
    </>
  );
}
