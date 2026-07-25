"use client";

import { Mail, Phone, MapPin, Clock, MessageSquare } from "lucide-react";
import { Container, Section, Reveal, Badge } from "@/components/ui";
import { AnimatedBackground } from "@/components/AnimatedBackground";
import { ContactForm } from "@/components/ContactForm";
import { useContent, Rich } from "@/lib/content";
import { site } from "@/lib/site";

export function ContactContent() {
  const { c, list } = useContent();
  const email = c("contactInfo.email", site.contact.email);
  const sales = c("contactInfo.sales", site.contact.sales);
  const phone = c("contactInfo.phone", site.contact.phone);
  const hours = c("contactInfo.hours", site.contact.hours);
  const addressLines = list<string>(
    "contactInfo.addressLines",
    site.contact.addressLines as unknown as string[],
  );

  return (
    <>
      <section className="relative overflow-hidden pt-32 pb-10 sm:pt-40">
        <AnimatedBackground />
        <Container>
          <div className="max-w-2xl">
            <Reveal>
              <Badge>
                <MessageSquare className="h-3.5 w-3.5 text-brand-500" />{" "}
                {c("contact.badge", "Contact us")}
              </Badge>
            </Reveal>
            <Reveal delay={0.05}>
              <h1 className="mt-5 text-4xl font-extrabold tracking-tight sm:text-5xl">
                <Rich text={c("contact.title", "Let's talk about your [[IT & AI]]")} />
              </h1>
            </Reveal>
            <Reveal delay={0.1}>
              <p className="mt-5 text-lg text-secondary-token">
                {c(
                  "contact.subtitle",
                  "Questions about Astra, managed services, or hardware? Send us a note and our team will get back to you.",
                )}
              </p>
            </Reveal>
          </div>
        </Container>
      </section>

      <Section className="pt-8 pb-28">
        <Container>
          <div className="grid gap-8 lg:grid-cols-5">
            {/* Contact info */}
            <div className="lg:col-span-2">
              <Reveal>
                <div className="space-y-4">
                  <InfoCard
                    icon={MapPin}
                    title={c("contact.visitTitle", "Visit us")}
                    lines={addressLines}
                  />
                  <InfoCard
                    icon={Mail}
                    title={c("contact.emailTitle", "Email us")}
                    lines={[email, sales]}
                    hrefs={[`mailto:${email}`, `mailto:${sales}`]}
                  />
                  <InfoCard
                    icon={Phone}
                    title={c("contact.callTitle", "Call us")}
                    lines={[phone]}
                    hrefs={[`tel:${phone.replace(/\s/g, "")}`]}
                  />
                  <InfoCard
                    icon={Clock}
                    title={c("contact.hoursTitle", "Business hours")}
                    lines={[hours]}
                  />
                </div>
              </Reveal>
            </div>

            {/* Form */}
            <div className="lg:col-span-3">
              <Reveal delay={0.1}>
                <ContactForm />
              </Reveal>
            </div>
          </div>
        </Container>
      </Section>
    </>
  );
}

function InfoCard({
  icon: Icon,
  title,
  lines,
  hrefs,
}: {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  lines: readonly string[];
  hrefs?: string[];
}) {
  return (
    <div className="flex gap-4 rounded-2xl border border-token bg-surface p-5">
      <div className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-brand-500/10 text-brand-500">
        <Icon className="h-5 w-5" />
      </div>
      <div>
        <h3 className="text-sm font-semibold">{title}</h3>
        <div className="mt-1 space-y-0.5">
          {lines.map((line, i) =>
            hrefs?.[i] ? (
              <a
                key={line}
                href={hrefs[i]}
                className="block text-sm text-secondary-token hover:text-brand-500"
              >
                {line}
              </a>
            ) : (
              <p key={line} className="text-sm text-secondary-token">
                {line}
              </p>
            ),
          )}
        </div>
      </div>
    </div>
  );
}
