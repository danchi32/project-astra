import type { Metadata } from "next";
import Link from "next/link";
import {
  Activity,
  ArrowRight,
  BadgeCheck,
  CheckCircle2,
  CircleGauge,
  FileClock,
  Laptop,
  ListChecks,
  SearchCheck,
  ShieldCheck,
  Wrench,
} from "lucide-react";
import { Badge, Button, Container, Section } from "@/components/ui";
import { bookDemo, site } from "@/lib/site";

export const metadata: Metadata = {
  title: "Windows Endpoint Automation & Self-Healing",
  description:
    "Automate Windows endpoint monitoring, evidence collection and approved remediation with ASTRA. Keep human control, verification and audit history.",
  keywords: [
    "Windows endpoint automation",
    "endpoint remediation automation",
    "Windows self healing",
    "automated endpoint management",
    "Windows fleet monitoring",
    "IT remediation platform",
  ],
  alternates: { canonical: "/windows-endpoint-automation/" },
  openGraph: {
    title: "Windows Endpoint Automation with Human Control",
    description:
      "Move from endpoint alert to verified action with live evidence, code-enforced approvals and allowlisted remediation.",
    url: "/windows-endpoint-automation/",
    type: "website",
  },
};

const workflow = [
  {
    icon: Activity,
    title: "Detect",
    body: "Collect device health and telemetry so recurring endpoint problems become visible early.",
  },
  {
    icon: SearchCheck,
    title: "Diagnose",
    body: "Combine the request, enterprise knowledge and live endpoint evidence before choosing an action.",
  },
  {
    icon: ListChecks,
    title: "Authorize",
    body: "Apply the action tier in backend code and request human approval whenever policy requires it.",
  },
  {
    icon: Wrench,
    title: "Remediate",
    body: "Send only known, allowlisted action identifiers to the independently protected Windows agent.",
  },
  {
    icon: BadgeCheck,
    title: "Verify",
    body: "Capture the result and device status instead of assuming that a command fixed the issue.",
  },
];

const useCases = [
  {
    title: "Routine desktop recovery",
    body: "Restart Explorer or approved user applications when a known failure matches policy.",
  },
  {
    title: "Network troubleshooting",
    body: "Collect network evidence and run permitted actions such as DNS flushes with the appropriate tier.",
  },
  {
    title: "Service recovery",
    body: "Restart only explicitly permitted Windows services, with backend and endpoint validation.",
  },
  {
    title: "Patch visibility",
    body: "Review update posture and rollout progress across the fleet before intervention.",
  },
  {
    title: "Endpoint reporting",
    body: "Bring device health, inventory, remediation activity and audit context into one portal.",
  },
  {
    title: "Controlled escalation",
    body: "Queue sensitive work for a technician or administrator instead of allowing the AI to exceed policy.",
  },
];

const faqs = [
  {
    question: "What is Windows endpoint automation?",
    answer:
      "Windows endpoint automation uses monitoring, policy and predefined actions to reduce repetitive device-management work. ASTRA adds an evidence-first reasoning loop, approval tiers and post-action verification.",
  },
  {
    question: "Can ASTRA execute arbitrary PowerShell commands?",
    answer:
      "No. ASTRA sends known remediation identifiers and parameters. The backend validates policy, and the Windows agent enforces its own allowlist before execution.",
  },
  {
    question: "How are high-risk actions controlled?",
    answer:
      "Every remediation is classified as automatic, approval-required or admin-only. The backend checks the actor and organization policy before an action can proceed.",
  },
  {
    question: "Does the agent require inbound firewall ports?",
    answer:
      "No. The Windows agent initiates outbound HTTPS traffic on port 443, so organizations do not need to expose inbound endpoint ports for ASTRA.",
  },
  {
    question: "How can an IT team evaluate endpoint automation safely?",
    answer:
      "Start with a limited device group, a small action catalogue and agreed success criteria. Review the evidence, approval history and verified outcomes before expanding the rollout.",
  },
];

const faqSchema = {
  "@context": "https://schema.org",
  "@type": "FAQPage",
  mainEntity: faqs.map((faq) => ({
    "@type": "Question",
    name: faq.question,
    acceptedAnswer: { "@type": "Answer", text: faq.answer },
  })),
};

export default function WindowsEndpointAutomationPage() {
  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(faqSchema) }}
      />

      <section className="aurora grain relative -mt-16 overflow-hidden pb-20 pt-28 sm:pt-36">
        <Container>
          <div className="max-w-4xl">
            <Badge>
              <Laptop className="h-3.5 w-3.5 text-brand-500" /> Windows endpoint automation
            </Badge>
            <h1 className="mt-5 text-4xl font-extrabold leading-tight tracking-tight sm:text-5xl lg:text-6xl">
              Turn Windows endpoint signals into controlled, verified action
            </h1>
            <p className="mt-6 max-w-3xl text-lg leading-relaxed text-secondary-token">
              ASTRA gathers live evidence, reasons against your knowledge and policy,
              and automates only the remediation your organization permits. Sensitive
              actions stay with authorized people, and every result is recorded.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Button href={bookDemo.href} external={bookDemo.external}>
                Plan an automation pilot <ArrowRight className="h-4 w-4" />
              </Button>
              <Button href={site.appUrl} variant="secondary" external>
                Start the 14-day trial
              </Button>
            </div>
            <div className="mt-7 flex flex-wrap gap-x-6 gap-y-2 text-sm text-muted-token">
              <span className="flex items-center gap-2"><ShieldCheck className="h-4 w-4 text-emerald-500" /> Code-enforced approval tiers</span>
              <span className="flex items-center gap-2"><FileClock className="h-4 w-4 text-emerald-500" /> Auditable commands</span>
              <span className="flex items-center gap-2"><CircleGauge className="h-4 w-4 text-emerald-500" /> Live fleet visibility</span>
            </div>
          </div>
        </Container>
      </section>

      <Section>
        <Container>
          <div className="mx-auto max-w-2xl text-center">
            <p className="text-sm font-semibold uppercase tracking-wider text-brand-500">Evidence before action</p>
            <h2 className="mt-3 text-3xl font-bold tracking-tight sm:text-4xl">One governed loop from detection to verification</h2>
            <p className="mt-4 text-secondary-token">Automation should reduce work without hiding why an action ran or who authorized it.</p>
          </div>
          <div className="mt-12 grid gap-4 md:grid-cols-5">
            {workflow.map(({ icon: Icon, title, body }, index) => (
              <article key={title} className="relative rounded-2xl border border-token bg-surface p-5">
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
          <div className="grid gap-12 lg:grid-cols-[0.8fr_1.2fr] lg:items-start">
            <div>
              <p className="text-sm font-semibold uppercase tracking-wider text-brand-500">Operational use cases</p>
              <h2 className="mt-3 text-3xl font-bold tracking-tight">Automate repeatable work, not judgment</h2>
              <p className="mt-4 leading-relaxed text-secondary-token">
                Start with low-risk, frequent endpoint problems. Keep broader changes behind approval while your team validates outcomes and expands policy deliberately.
              </p>
              <Link href="/security/" className="mt-6 inline-flex items-center gap-2 text-sm font-semibold text-brand-500 hover:underline">
                Review security controls <ArrowRight className="h-4 w-4" />
              </Link>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              {useCases.map((useCase) => (
                <article key={useCase.title} className="rounded-2xl border border-token bg-app p-5">
                  <h3 className="font-bold">{useCase.title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-secondary-token">{useCase.body}</p>
                </article>
              ))}
            </div>
          </div>
        </Container>
      </Section>

      <Section>
        <Container>
          <div className="grid gap-10 rounded-3xl border border-token bg-surface p-8 lg:grid-cols-2 lg:p-12">
            <div>
              <p className="text-sm font-semibold uppercase tracking-wider text-brand-500">Pilot framework</p>
              <h2 className="mt-3 text-3xl font-bold tracking-tight">Prove value on a controlled device group</h2>
              <p className="mt-4 text-secondary-token">A useful pilot measures operational outcomes while limiting scope and risk.</p>
            </div>
            <ul className="space-y-3">
              {[
                "Choose a representative Windows device group",
                "Select frequent issues and permitted remediation actions",
                "Agree who can approve sensitive actions",
                "Track evidence collected, actions attempted and verified outcomes",
                "Review exceptions before expanding the rollout",
              ].map((item) => (
                <li key={item} className="flex items-start gap-3">
                  <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-500" />
                  <span className="text-sm text-secondary-token">{item}</span>
                </li>
              ))}
            </ul>
          </div>
        </Container>
      </Section>

      <Section className="bg-surface">
        <Container>
          <div className="mx-auto max-w-3xl">
            <div className="text-center">
              <p className="text-sm font-semibold uppercase tracking-wider text-brand-500">Frequently asked questions</p>
              <h2 className="mt-3 text-3xl font-bold tracking-tight">Windows automation with clear boundaries</h2>
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
            <h2 className="text-3xl font-bold">Map your first endpoint automation workflow</h2>
            <p className="mx-auto mt-4 max-w-xl text-white/85">Bring one recurring Windows issue to a 30-minute session. We will map the evidence, approval tier, allowed action and verification step.</p>
            <a href={bookDemo.href} target={bookDemo.external ? "_blank" : undefined} rel={bookDemo.external ? "noopener" : undefined} className="mt-8 inline-flex items-center gap-2 rounded-xl bg-white px-6 py-3 text-sm font-semibold text-brand-700">
              Book the workflow session <ArrowRight className="h-4 w-4" />
            </a>
          </div>
        </Container>
      </Section>
    </>
  );
}
