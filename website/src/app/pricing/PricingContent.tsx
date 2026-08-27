"use client";

import { HelpCircle } from "lucide-react";
import { Container, Section, Reveal, Badge, SectionHeading } from "@/components/ui";
import { AnimatedBackground } from "@/components/AnimatedBackground";
import { PricingPlans } from "@/components/PricingPlans";
import { useContent, Rich } from "@/lib/content";

type Faq = { q: string; a: string };
const faqDefaults: Faq[] = [
  {
    q: "How is ASTRA priced?",
    a: "Per device, per month. Essential covers inventory, telemetry and patching; Professional adds the AI engine and automatic self-healing; Expert adds compliance, fleet-wide remediation and full audit. Annual billing saves about 17%.",
  },
  {
    q: "Which plan should I choose?",
    a: "Most teams start on Professional — it's where the AI actually fixes issues on its own. Choose Essential if you mainly need visibility and patching, and Expert if you have compliance or audit requirements.",
  },
  {
    q: "Is there a free trial?",
    a: "Yes — start with a free trial, no credit card required to explore the platform.",
  },
  {
    q: "Can I change plans later?",
    a: "Absolutely. Upgrade or downgrade at any time; billing adjusts on your next cycle based on your active devices.",
  },
  {
    q: "Do you offer volume pricing?",
    a: "Yes. For fleets above 50 devices, contact sales for volume pricing and a guided rollout.",
  },
  {
    q: "Do you supply the hardware too?",
    a: "Yes — Technomate is also a laptop and hardware supplier. Bundle devices with ASTRA for a fully managed rollout.",
  },
];

export function PricingContent() {
  const { c, list } = useContent();
  const faqs = list<Faq>("pricing.faqs", faqDefaults);

  return (
    <>
      <section className="aurora grain relative -mt-16 overflow-hidden pt-28 pb-10 sm:pt-36">
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
                  "Pay per device. Start with visibility, add AI self-healing, then compliance as you grow.",
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
