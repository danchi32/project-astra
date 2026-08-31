import type { Metadata } from "next";
import Link from "next/link";
import {
  Activity, ArrowRight, BadgeCheck, Building2, CheckCircle2,
  CircleGauge, FileClock, Laptop, ListChecks, ShieldCheck, Users, Wrench,
} from "lucide-react";
import { Badge, Button, Container, Section } from "@/components/ui";
import { bookDemo, site } from "@/lib/site";

export const metadata: Metadata = {
  title: "IT Support Software for 50–500 Employee Teams",
  description:
    "ASTRA helps Indian organizations with 50–500 employees monitor Windows endpoints, reduce repetitive IT work and automate approved remediation.",
  keywords: [
    "IT support software India",
    "IT support for 50 employees",
    "IT management for 500 employees",
    "Windows endpoint management India",
    "IT automation for growing companies",
    "AI IT operations platform",
  ],
  alternates: { canonical: "/it-support-50-500-employees/" },
  openGraph: {
    title: "IT Support Software for Growing 50–500 Employee Organizations",
    description:
      "Give a lean IT team fleet visibility, evidence-first diagnosis and controlled Windows remediation across India.",
    url: "/it-support-50-500-employees/",
    type: "website",
  },
};

const pressures = [
  { icon: Users, title: "More employees, same IT team", body: "Support demand grows faster than the team available to investigate every Windows issue." },
  { icon: Laptop, title: "A distributed device fleet", body: "Remote and office endpoints make manual inventory, health checks and troubleshooting harder." },
  { icon: ListChecks, title: "Inconsistent operational work", body: "Patching, offboarding and repeat fixes depend on individual memory or disconnected scripts." },
];

const capabilities = [
  "Live Windows endpoint health and telemetry",
  "Hardware, software and service inventory",
  "Evidence-first AI diagnosis",
  "Automatic, approval-required and admin-only action tiers",
  "Allowlisted remediation commands",
  "Patch and update visibility",
  "Joiner and secure offboarding workflows",
  "Audit history for actions and approvals",
];

const rollout = [
  ["Select", "Choose a representative Windows device group and the recurring issues worth testing."],
  ["Control", "Define which actions are automatic, which need approval and who is authorized."],
  ["Measure", "Track evidence collection, action attempts, verified outcomes and exceptions."],
  ["Expand", "Add devices and workflows only after the team reviews the pilot evidence."],
];

const faqs = [
  {
    question: "Is ASTRA available across India?",
    answer:
      "Yes. ASTRA is cloud-delivered software for supported Windows endpoints and can be evaluated and deployed by organizations across India. Optional managed or on-site services are scoped separately by location.",
  },
  {
    question: "Why is ASTRA suited to organizations with 50–500 employees?",
    answer:
      "At this stage, device count and support demand often grow faster than the internal IT team. ASTRA provides shared fleet visibility and controlled automation without requiring every routine issue to be handled manually.",
  },
  {
    question: "Does ASTRA replace our IT administrators?",
    answer:
      "No. ASTRA gathers evidence and handles permitted repeat work. Administrators keep control of sensitive remediation, exceptions, policy and broader infrastructure decisions.",
  },
  {
    question: "Can ASTRA work alongside our current tools?",
    answer:
      "A pilot can evaluate ASTRA alongside the current environment. Integration and coexistence requirements should be documented during assessment rather than assumed before reviewing your toolset.",
  },
  {
    question: "How can we evaluate ASTRA safely?",
    answer:
      "Start with a limited device group, named approvers, a small action catalogue and agreed success criteria. ASTRA also offers a 14-day full-product trial without a credit card.",
  },
];

const schema = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "SoftwareApplication",
      name: "ASTRA",
      applicationCategory: "BusinessApplication",
      operatingSystem: "Windows 10, Windows 11",
      url: "https://technomateai.com/it-support-50-500-employees/",
      description: metadata.description,
      audience: {
        "@type": "BusinessAudience",
        audienceType: "Organizations with 50 to 500 employees",
        geographicArea: { "@type": "Country", name: "India" },
      },
      offers: { "@type": "Offer", price: "0", priceCurrency: "USD", description: "14-day trial" },
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

export default function ItSupportForGrowingOrganizationsPage() {
  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }} />

      <section className="aurora grain relative -mt-16 overflow-hidden pb-20 pt-28 sm:pt-36">
        <Container>
          <div className="grid items-center gap-12 lg:grid-cols-[1.15fr_0.85fr]">
            <div>
              <Badge><Building2 className="h-3.5 w-3.5 text-brand-500" /> Built for growing organizations</Badge>
              <h1 className="mt-5 text-4xl font-extrabold leading-tight tracking-tight sm:text-5xl lg:text-6xl">
                Scale IT support across 50–500 employees without losing control
              </h1>
              <p className="mt-6 max-w-3xl text-lg leading-relaxed text-secondary-token">
                ASTRA gives lean IT teams across India one view of Windows endpoint health, evidence-first diagnosis and approved remediation—so growth does not turn every routine issue into manual work.
              </p>
              <div className="mt-8 flex flex-wrap gap-3">
                <Button href={bookDemo.href} external={bookDemo.external}>Plan a limited-device pilot <ArrowRight className="h-4 w-4" /></Button>
                <Button href={site.appUrl} variant="secondary" external>Start the 14-day trial</Button>
              </div>
              <div className="mt-7 flex flex-wrap gap-x-6 gap-y-2 text-sm text-muted-token">
                <span className="flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-emerald-500" /> Available across India</span>
                <span className="flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-emerald-500" /> No credit card</span>
                <span className="flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-emerald-500" /> Windows 10 and 11</span>
              </div>
            </div>

            <aside className="rounded-3xl border border-token bg-surface p-7 shadow-xl">
              <p className="text-sm font-semibold uppercase tracking-wider text-brand-500">One operational view</p>
              <h2 className="mt-3 text-2xl font-bold">From device signal to verified outcome</h2>
              <ol className="mt-7 space-y-4">
                {["Collect live endpoint evidence", "Search approved operational knowledge", "Apply the code-enforced action tier", "Run only an allowlisted remediation", "Verify and record the result"].map((step, index) => (
                  <li key={step} className="flex items-center gap-3">
                    <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-brand-600 text-xs font-bold text-white">{index + 1}</span>
                    <span className="text-sm text-secondary-token">{step}</span>
                  </li>
                ))}
              </ol>
            </aside>
          </div>
        </Container>
      </section>

      <Section>
        <Container>
          <div className="mx-auto max-w-2xl text-center">
            <p className="text-sm font-semibold uppercase tracking-wider text-brand-500">The growth-stage IT gap</p>
            <h2 className="mt-3 text-3xl font-bold tracking-tight sm:text-4xl">Your fleet grows before your operating model catches up</h2>
          </div>
          <div className="mt-12 grid gap-6 md:grid-cols-3">
            {pressures.map(({ icon: Icon, title, body }) => (
              <article key={title} className="rounded-2xl border border-token bg-surface p-7">
                <div className="grid h-11 w-11 place-items-center rounded-xl bg-brand-500/10 text-brand-500"><Icon className="h-5 w-5" /></div>
                <h3 className="mt-5 text-lg font-bold">{title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-secondary-token">{body}</p>
              </article>
            ))}
          </div>
        </Container>
      </Section>

      <Section className="bg-surface">
        <Container>
          <div className="grid gap-12 lg:grid-cols-2 lg:items-center">
            <div>
              <p className="text-sm font-semibold uppercase tracking-wider text-brand-500">ASTRA for the Windows fleet</p>
              <h2 className="mt-3 text-3xl font-bold tracking-tight sm:text-4xl">Standardize repeat work while people handle judgment</h2>
              <p className="mt-4 leading-relaxed text-secondary-token">
                The platform combines endpoint evidence, enterprise knowledge and controlled automation. Sensitive actions cannot be lowered into an automatic tier by the model.
              </p>
              <div className="mt-7 flex flex-wrap gap-3">
                <Button href="/windows-endpoint-automation/">Explore endpoint automation</Button>
                <Button href="/security/" variant="secondary">Review security controls</Button>
              </div>
            </div>
            <ul className="grid gap-3 sm:grid-cols-2">
              {capabilities.map((capability) => (
                <li key={capability} className="flex items-start gap-3 rounded-xl border border-token bg-app px-4 py-3">
                  <BadgeCheck className="mt-0.5 h-5 w-5 shrink-0 text-emerald-500" />
                  <span className="text-sm text-secondary-token">{capability}</span>
                </li>
              ))}
            </ul>
          </div>
        </Container>
      </Section>

      <Section>
        <Container>
          <div className="grid gap-10 lg:grid-cols-[0.8fr_1.2fr] lg:items-center">
            <div>
              <p className="text-sm font-semibold uppercase tracking-wider text-brand-500">Low-risk evaluation</p>
              <h2 className="mt-3 text-3xl font-bold tracking-tight">Prove the workflow before expanding</h2>
              <p className="mt-4 text-secondary-token">A useful pilot limits devices and actions while giving your team enough evidence to judge operational fit.</p>
              <Link href="/self-healing-it/" className="mt-6 inline-flex items-center gap-2 text-sm font-semibold text-brand-500 hover:underline">Understand self-healing IT <ArrowRight className="h-4 w-4" /></Link>
            </div>
            <div className="space-y-4">
              {rollout.map(([title, body], index) => (
                <article key={title} className="flex gap-4 rounded-2xl border border-token bg-surface p-5">
                  <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-brand-600 text-sm font-bold text-white">{index + 1}</span>
                  <div><h3 className="font-bold">{title}</h3><p className="mt-1 text-sm leading-relaxed text-secondary-token">{body}</p></div>
                </article>
              ))}
            </div>
          </div>
        </Container>
      </Section>

      <Section className="bg-surface">
        <Container>
          <div className="mx-auto max-w-3xl">
            <div className="text-center">
              <p className="text-sm font-semibold uppercase tracking-wider text-brand-500">Frequently asked questions</p>
              <h2 className="mt-3 text-3xl font-bold tracking-tight">Software rollout across India, with clear boundaries</h2>
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
            <ShieldCheck className="mx-auto h-10 w-10" />
            <h2 className="mt-4 text-3xl font-bold">Map ASTRA to your current IT workload</h2>
            <p className="mx-auto mt-4 max-w-xl text-white/85">Bring your device count, recurring Windows issues and approval requirements to a 30-minute pilot-planning session.</p>
            <a href={bookDemo.href} target={bookDemo.external ? "_blank" : undefined} rel={bookDemo.external ? "noopener" : undefined} className="mt-8 inline-flex items-center gap-2 rounded-xl bg-white px-6 py-3 text-sm font-semibold text-brand-700">Book the pilot session <ArrowRight className="h-4 w-4" /></a>
          </div>
        </Container>
      </Section>
    </>
  );
}
