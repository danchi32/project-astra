import type { Metadata } from "next";
import Link from "next/link";
import {
  Activity, ArrowRight, BadgeCheck, BrainCircuit, ClipboardCheck,
  FileClock, Gauge, ListChecks, SearchCheck, ShieldCheck, Wrench,
} from "lucide-react";
import { Badge, Button, Container, Section } from "@/components/ui";
import { bookDemo, site } from "@/lib/site";

export const metadata: Metadata = {
  title: "Self-Healing IT Automation for Windows Teams",
  description:
    "Reduce repetitive Windows support work with evidence-first self-healing IT. ASTRA controls approvals, allowlists actions and verifies every attempted fix.",
  keywords: [
    "self-healing IT", "self-healing IT automation", "automated IT remediation",
    "proactive IT support", "Windows self-healing", "AI IT operations",
  ],
  alternates: { canonical: "/self-healing-it/" },
  openGraph: {
    title: "Self-Healing IT That Keeps Your Team in Control",
    description: "Turn live endpoint evidence into governed remediation and verified outcomes with ASTRA.",
    url: "/self-healing-it/",
    type: "website",
  },
};

const stages = [
  { icon: Activity, title: "Observe", body: "Collect current endpoint health, events and service state." },
  { icon: SearchCheck, title: "Understand", body: "Use the request, live evidence and approved knowledge to diagnose the issue." },
  { icon: ShieldCheck, title: "Control", body: "Apply the code-enforced action tier before any remediation can run." },
  { icon: Wrench, title: "Act", body: "Execute only a defined, allowlisted action with validated parameters." },
  { icon: ClipboardCheck, title: "Verify", body: "Check the result and record what changed instead of assuming success." },
];

const outcomes = [
  { icon: Gauge, title: "Reduce manual triage", body: "Give technicians evidence and context before they spend time reproducing a routine issue." },
  { icon: BrainCircuit, title: "Apply policy consistently", body: "Use the same approval boundaries across devices rather than relying on ad hoc scripts." },
  { icon: BadgeCheck, title: "Keep humans on risky work", body: "Route approval-required and admin-only actions to the people authorized to decide." },
  { icon: FileClock, title: "Create an audit trail", body: "Retain the request, evidence, authorization, execution result and verification context." },
];

const examples = [
  ["Explorer or approved app recovery", "Automatic when the known condition and organization policy allow it."],
  ["Approved Windows service restart", "Automatic only for explicitly allowlisted services and parameters."],
  ["Office repair or driver update", "Held for human approval before execution."],
  ["Registry, BIOS or firmware changes", "Restricted to an authorized administrator."],
];

const faqs = [
  {
    question: "What does self-healing IT mean?",
    answer: "Self-healing IT detects a known issue, gathers evidence, applies a permitted remediation and verifies the result. In ASTRA, it does not mean unrestricted autonomous access to devices.",
  },
  {
    question: "Does ASTRA replace an IT team?",
    answer: "No. ASTRA reduces repetitive evidence collection and routine remediation while technicians retain control of sensitive decisions, exceptions and broader operational work.",
  },
  {
    question: "How does ASTRA decide what can run automatically?",
    answer: "Each remediation has an automatic, approval-required or admin-only tier. The backend validates the action, actor and organization policy, while the endpoint agent separately enforces its allowlist.",
  },
  {
    question: "What happens when a remediation does not work?",
    answer: "ASTRA records the attempted action and verification result. The issue can then be escalated with the available evidence rather than being reported as resolved without confirmation.",
  },
  {
    question: "Can we start with a small rollout?",
    answer: "Yes. A limited-device pilot can begin with frequent, low-risk issues, named approvers and agreed success criteria before the organization expands the action catalogue.",
  },
];

const schema = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "SoftwareApplication",
      name: "ASTRA Self-Healing IT",
      applicationCategory: "BusinessApplication",
      operatingSystem: "Windows 10, Windows 11",
      url: "https://technomateai.com/self-healing-it/",
      description: metadata.description,
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

export default function SelfHealingItPage() {
  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }} />
      <section className="aurora grain relative -mt-16 overflow-hidden pb-20 pt-28 sm:pt-36">
        <Container>
          <div className="max-w-4xl">
            <Badge><BrainCircuit className="h-3.5 w-3.5 text-brand-500" /> Self-healing IT</Badge>
            <h1 className="mt-5 text-4xl font-extrabold leading-tight tracking-tight sm:text-5xl lg:text-6xl">
              Resolve routine IT issues before they become another manual ticket
            </h1>
            <p className="mt-6 max-w-3xl text-lg leading-relaxed text-secondary-token">
              ASTRA turns live Windows endpoint evidence into a controlled remediation, then verifies the outcome. Your team defines what can run automatically and what must wait for approval.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Button href={bookDemo.href} external={bookDemo.external}>Plan a self-healing pilot <ArrowRight className="h-4 w-4" /></Button>
              <Button href={site.appUrl} variant="secondary" external>Start the 14-day trial</Button>
            </div>
            <div className="mt-7 flex flex-wrap gap-x-6 gap-y-2 text-sm text-muted-token">
              <span className="flex items-center gap-2"><ShieldCheck className="h-4 w-4 text-emerald-500" /> Three approval tiers</span>
              <span className="flex items-center gap-2"><ListChecks className="h-4 w-4 text-emerald-500" /> Allowlisted actions</span>
              <span className="flex items-center gap-2"><BadgeCheck className="h-4 w-4 text-emerald-500" /> Post-action verification</span>
            </div>
          </div>
        </Container>
      </section>

      <Section>
        <Container>
          <div className="mx-auto max-w-2xl text-center">
            <p className="text-sm font-semibold uppercase tracking-wider text-brand-500">A closed operational loop</p>
            <h2 className="mt-3 text-3xl font-bold tracking-tight sm:text-4xl">Self-healing means a permitted fix followed by proof</h2>
            <p className="mt-4 text-secondary-token">A command is not a resolution until the result has been checked and recorded.</p>
          </div>
          <div className="mt-12 grid gap-4 md:grid-cols-5">
            {stages.map(({ icon: Icon, title, body }, index) => (
              <article key={title} className="rounded-2xl border border-token bg-surface p-5">
                <span className="text-xs font-bold text-brand-500">0{index + 1}</span>
                <Icon className="mt-4 h-6 w-6 text-brand-500" />
                <h3 className="mt-3 font-bold">{title}</h3>
                <p className="mt-2 text-xs leading-relaxed text-secondary-token">{body}</p>
              </article>
            ))}
          </div>
        </Container>
      </Section>

      <Section className="bg-surface">
        <Container>
          <div className="grid gap-10 lg:grid-cols-2 lg:items-center">
            <div>
              <p className="text-sm font-semibold uppercase tracking-wider text-brand-500">Operational value</p>
              <h2 className="mt-3 text-3xl font-bold tracking-tight">Give a lean IT team more time for exceptions</h2>
              <p className="mt-4 leading-relaxed text-secondary-token">ASTRA focuses automation on frequent, defined work. It helps the team investigate faster without pretending every incident should be autonomous.</p>
              <Link href="/windows-endpoint-automation/" className="mt-6 inline-flex items-center gap-2 text-sm font-semibold text-brand-500 hover:underline">Explore Windows endpoint automation <ArrowRight className="h-4 w-4" /></Link>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              {outcomes.map(({ icon: Icon, title, body }) => (
                <article key={title} className="rounded-2xl border border-token bg-app p-5">
                  <Icon className="h-6 w-6 text-brand-500" />
                  <h3 className="mt-3 font-bold">{title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-secondary-token">{body}</p>
                </article>
              ))}
            </div>
          </div>
        </Container>
      </Section>

      <Section>
        <Container>
          <div className="grid gap-10 lg:grid-cols-[0.8fr_1.2fr]">
            <div>
              <p className="text-sm font-semibold uppercase tracking-wider text-brand-500">Boundaries by design</p>
              <h2 className="mt-3 text-3xl font-bold tracking-tight">Match autonomy to operational risk</h2>
              <p className="mt-4 text-secondary-token">The model cannot promote a sensitive action into a lower tier. Authorization is enforced by application code and endpoint allowlists.</p>
              <Link href="/security/" className="mt-6 inline-flex items-center gap-2 text-sm font-semibold text-brand-500 hover:underline">Review ASTRA security controls <ArrowRight className="h-4 w-4" /></Link>
            </div>
            <div className="overflow-hidden rounded-2xl border border-token">
              {examples.map(([action, control]) => (
                <div key={action} className="grid gap-2 border-b border-token bg-surface p-5 last:border-b-0 sm:grid-cols-[0.8fr_1.2fr]">
                  <h3 className="font-semibold">{action}</h3>
                  <p className="text-sm text-secondary-token">{control}</p>
                </div>
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
              <h2 className="mt-3 text-3xl font-bold tracking-tight">Evaluate self-healing IT with clear expectations</h2>
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
            <h2 className="text-3xl font-bold">Choose one repetitive issue for your first pilot</h2>
            <p className="mx-auto mt-4 max-w-xl text-white/85">In a 30-minute session, we will map the evidence, action boundary, approver and verification step for a controlled Windows device group.</p>
            <a href={bookDemo.href} target={bookDemo.external ? "_blank" : undefined} rel={bookDemo.external ? "noopener" : undefined} className="mt-8 inline-flex items-center gap-2 rounded-xl bg-white px-6 py-3 text-sm font-semibold text-brand-700">Book the pilot session <ArrowRight className="h-4 w-4" /></a>
          </div>
        </Container>
      </Section>
    </>
  );
}
