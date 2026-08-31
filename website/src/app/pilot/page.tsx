import type { Metadata } from "next";
import Link from "next/link";
import {
  ArrowRight, BadgeCheck, CalendarDays, CheckCircle2, ClipboardCheck,
  Gauge, Laptop, ListChecks, ShieldCheck, Users, Wrench,
} from "lucide-react";
import { Badge, Button, Container, Section } from "@/components/ui";
import { bookDemo, site } from "@/lib/site";

export const metadata: Metadata = {
  title: "Free 14-Day ASTRA Windows Endpoint Pilot",
  description:
    "Evaluate ASTRA on up to 10 Windows devices with guided setup, controlled remediation, verification and a final rollout review—free for 14 days.",
  keywords: [
    "free IT automation pilot",
    "Windows endpoint pilot",
    "ASTRA free trial",
    "endpoint automation proof of concept",
    "AI IT support pilot India",
  ],
  alternates: { canonical: "/pilot/" },
  openGraph: {
    title: "Free 14-Day ASTRA Controlled Endpoint Pilot",
    description:
      "Test evidence-first Windows automation on up to 10 devices with clear approvals, verified outcomes and no credit card.",
    url: "/pilot/",
    type: "website",
  },
};

const terms = [
  { icon: Laptop, value: "Up to 10", label: "Windows devices" },
  { icon: CalendarDays, value: "14 days", label: "From first device report" },
  { icon: Users, value: "Guided", label: "Kickoff and reviews" },
  { icon: BadgeCheck, value: "Free", label: "No credit card" },
];

const stages = [
  ["Plan", "Choose the device group, three to five recurring issues and the people authorized to approve sensitive work."],
  ["Connect", "Enroll supported Windows devices and confirm that endpoint health and evidence are reporting correctly."],
  ["Evaluate", "Run the agreed workflows within automatic, approval-required and administrator-only boundaries."],
  ["Decide", "Review verified outcomes, exceptions and operating fit before expanding, continuing or removing the agent."],
];

const included = [
  "Pilot-planning session for devices, issues and action boundaries",
  "ASTRA access for up to 10 supported Windows endpoints",
  "Guidance for Windows agent deployment and removal",
  "Live endpoint health, telemetry and inventory visibility",
  "Evidence-first diagnosis using endpoint context and approved knowledge",
  "Code-enforced automatic, approval-required and admin-only tiers",
  "Allowlisted endpoint actions and parameter validation",
  "Audit history for actions, approvals and execution results",
  "Midpoint review and final rollout recommendation",
];

const success = [
  "Pilot devices report successfully or have a documented exception",
  "Selected issues provide useful evidence before technician investigation",
  "Approval-required actions remain blocked until an authorized person approves",
  "The endpoint rejects unknown actions and invalid parameters",
  "Every attempted remediation keeps an attributable audit record",
  "Verification separates resolved, failed and inconclusive outcomes",
  "No critical business workflow is disrupted by the agreed action catalogue",
];

const faqs = [
  {
    question: "Is the guided ASTRA pilot really free?",
    answer:
      "Yes. The 14-day guided pilot for up to 10 supported Windows devices is free and does not require a credit card. A paid rollout begins only after separate approval.",
  },
  {
    question: "When do the 14 days begin?",
    answer:
      "The pilot begins when the first approved Windows device reports successfully, not when the account is created.",
  },
  {
    question: "Which devices can join the pilot?",
    answer:
      "The ASTRA endpoint agent currently supports 64-bit Windows 10 and Windows 11 devices. The pilot group should represent normal users without beginning on business-critical or unusually sensitive machines.",
  },
  {
    question: "Does ASTRA run every fix automatically?",
    answer:
      "No. Each action is classified as automatic, approval-required or administrator-only. Eligible automatic actions can be acknowledged and executed immediately when an endpoint is online, but sensitive actions remain with authorized people.",
  },
  {
    question: "What happens at the end of the pilot?",
    answer:
      "The final review documents verified outcomes, exceptions and next steps. You can expand, continue with changes, run ASTRA alongside existing tools or stop and remove the agent. No paid rollout starts automatically.",
  },
];

const schema = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "Service",
      name: "ASTRA Controlled Endpoint Pilot",
      url: "https://technomateai.com/pilot/",
      provider: { "@id": "https://technomateai.com/#organization" },
      areaServed: { "@type": "Country", name: "India" },
      description: metadata.description,
      offers: {
        "@type": "Offer",
        price: "0",
        priceCurrency: "USD",
        description: "Free 14-day guided pilot for up to 10 supported Windows devices",
      },
    },
    {
      "@type": "FAQPage",
      mainEntity: faqs.map((faq) => ({
        "@type": "Question",
        name: faq.question,
        acceptedAnswer: { "@type": "Answer", text: faq.answer },
      })),
    },
  ],
};

export default function PilotPage() {
  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }} />

      <section className="aurora grain relative -mt-16 overflow-hidden pb-20 pt-28 sm:pt-36">
        <Container>
          <div className="mx-auto max-w-4xl text-center">
            <Badge><ShieldCheck className="h-3.5 w-3.5 text-brand-500" /> Controlled endpoint pilot</Badge>
            <h1 className="mt-5 text-4xl font-extrabold leading-tight tracking-tight sm:text-5xl lg:text-6xl">
              Prove ASTRA on 10 Windows devices before a wider rollout
            </h1>
            <p className="mx-auto mt-6 max-w-3xl text-lg leading-relaxed text-secondary-token">
              Run a free, guided 14-day pilot with agreed issue types, clear approval boundaries and verification after every attempted fix. Keep the evidence and make a rollout decision without an automatic paid commitment.
            </p>
            <div className="mt-8 flex flex-wrap justify-center gap-3">
              <Button href={bookDemo.href} external={bookDemo.external}>Book the pilot-planning session <ArrowRight className="h-4 w-4" /></Button>
              <Button href={site.appUrl} variant="secondary" external>Create the trial account</Button>
            </div>
          </div>

          <div className="mx-auto mt-12 grid max-w-5xl gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {terms.map(({ icon: Icon, value, label }) => (
              <article key={label} className="rounded-2xl border border-token bg-surface p-5 text-center">
                <Icon className="mx-auto h-6 w-6 text-brand-500" />
                <p className="mt-3 text-2xl font-bold">{value}</p>
                <p className="mt-1 text-sm text-secondary-token">{label}</p>
              </article>
            ))}
          </div>
        </Container>
      </section>

      <Section>
        <Container>
          <div className="mx-auto max-w-2xl text-center">
            <p className="text-sm font-semibold uppercase tracking-wider text-brand-500">How the pilot works</p>
            <h2 className="mt-3 text-3xl font-bold tracking-tight sm:text-4xl">A limited evaluation with a clear decision at the end</h2>
          </div>
          <div className="mt-12 grid gap-5 md:grid-cols-4">
            {stages.map(([title, body], index) => (
              <article key={title} className="rounded-2xl border border-token bg-surface p-6">
                <span className="grid h-9 w-9 place-items-center rounded-full bg-brand-600 text-sm font-bold text-white">{index + 1}</span>
                <h3 className="mt-4 text-lg font-bold">{title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-secondary-token">{body}</p>
              </article>
            ))}
          </div>
        </Container>
      </Section>

      <Section className="bg-surface">
        <Container>
          <div className="grid gap-12 lg:grid-cols-2 lg:items-start">
            <div>
              <p className="text-sm font-semibold uppercase tracking-wider text-brand-500">Included in the free pilot</p>
              <h2 className="mt-3 text-3xl font-bold tracking-tight">Software, guidance and review—not an unattended trial</h2>
              <p className="mt-4 text-secondary-token">The pilot is structured to help your IT owner evaluate real operating fit while keeping the device group and action catalogue controlled.</p>
              <Link href="/security/" className="mt-6 inline-flex items-center gap-2 text-sm font-semibold text-brand-500 hover:underline">
                Review ASTRA security controls <ArrowRight className="h-4 w-4" />
              </Link>
            </div>
            <ul className="grid gap-3">
              {included.map((item) => (
                <li key={item} className="flex items-start gap-3 rounded-xl border border-token bg-app px-4 py-3">
                  <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-500" />
                  <span className="text-sm text-secondary-token">{item}</span>
                </li>
              ))}
            </ul>
          </div>
        </Container>
      </Section>

      <Section>
        <Container>
          <div className="grid gap-12 lg:grid-cols-[0.8fr_1.2fr] lg:items-center">
            <div>
              <Badge><Wrench className="h-3.5 w-3.5 text-brand-500" /> Evidence before expansion</Badge>
              <h2 className="mt-5 text-3xl font-bold tracking-tight">Measure workflow quality, not the number of commands</h2>
              <p className="mt-4 leading-relaxed text-secondary-token">
                A useful pilot shows why an action was selected, whether policy was enforced and whether the endpoint reached the expected state.
              </p>
              <Link href="/blog/windows-endpoint-automation-pilot-checklist/" className="mt-6 inline-flex items-center gap-2 text-sm font-semibold text-brand-500 hover:underline">
                Read the full pilot checklist <ArrowRight className="h-4 w-4" />
              </Link>
            </div>
            <div className="rounded-2xl border border-token bg-surface p-7">
              <div className="flex items-center gap-3"><ClipboardCheck className="h-6 w-6 text-brand-500" /><h3 className="text-xl font-bold">Recommended success criteria</h3></div>
              <ul className="mt-6 space-y-3">
                {success.map((item) => (
                  <li key={item} className="flex items-start gap-3">
                    <ListChecks className="mt-0.5 h-5 w-5 shrink-0 text-brand-500" />
                    <span className="text-sm leading-relaxed text-secondary-token">{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </Container>
      </Section>

      <Section className="bg-surface">
        <Container>
          <div className="mx-auto max-w-3xl">
            <div className="text-center">
              <p className="text-sm font-semibold uppercase tracking-wider text-brand-500">Frequently asked questions</p>
              <h2 className="mt-3 text-3xl font-bold tracking-tight">Clear terms before the first device connects</h2>
            </div>
            <div className="mt-10 space-y-4">
              {faqs.map((faq) => (
                <article key={faq.question} className="rounded-2xl border border-token bg-app p-6">
                  <h3 className="font-bold">{faq.question}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-secondary-token">{faq.answer}</p>
                </article>
              ))}
            </div>
          </div>
        </Container>
      </Section>

      <Section className="pb-28">
        <Container>
          <div className="rounded-3xl bg-gradient-to-br from-brand-600 to-violet-600 px-8 py-14 text-center text-white">
            <Gauge className="mx-auto h-10 w-10" />
            <h2 className="mt-4 text-3xl font-bold">Bring one recurring Windows issue</h2>
            <p className="mx-auto mt-4 max-w-xl text-white/85">We will map the evidence, permitted action, approver and verification step for your free 10-device pilot.</p>
            <a href={bookDemo.href} target={bookDemo.external ? "_blank" : undefined} rel={bookDemo.external ? "noopener" : undefined} className="mt-8 inline-flex items-center gap-2 rounded-xl bg-white px-6 py-3 text-sm font-semibold text-brand-700">
              Book the pilot-planning session <ArrowRight className="h-4 w-4" />
            </a>
          </div>
        </Container>
      </Section>
    </>
  );
}
