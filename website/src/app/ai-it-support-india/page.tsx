import type { Metadata } from "next";
import Link from "next/link";
import {
  Activity,
  ArrowRight,
  CheckCircle2,
  Clock3,
  Laptop,
  MapPin,
  ShieldCheck,
  Sparkles,
  Wrench,
} from "lucide-react";
import { Badge, Button, Container, Section } from "@/components/ui";
import { bookDemo, site } from "@/lib/site";

export const metadata: Metadata = {
  title: "AI IT Support India for Windows Teams",
  description:
    "AI-powered IT support for growing Indian businesses. Monitor Windows endpoints, reduce manual triage and automate approved fixes with ASTRA and Technomate.",
  keywords: [
    "AI IT support India",
    "managed IT services India",
    "Windows endpoint support",
    "IT automation India",
    "managed IT services Noida",
    "AI system administrator",
  ],
  alternates: { canonical: "/ai-it-support-india/" },
  openGraph: {
    title: "AI IT Support India for Windows Teams",
    description:
      "Combine ASTRA endpoint automation with India-based managed IT support for a safer, faster response to everyday Windows issues.",
    url: "/ai-it-support-india/",
    type: "website",
  },
};

const outcomes = [
  {
    icon: Clock3,
    title: "Reduce manual triage",
    body: "ASTRA gathers device evidence and relevant knowledge before a technician has to investigate the issue.",
  },
  {
    icon: Wrench,
    title: "Resolve approved routine issues",
    body: "Known low-risk actions can run automatically while sensitive fixes wait for an authorized person.",
  },
  {
    icon: Activity,
    title: "See the whole Windows fleet",
    body: "Monitor device health, telemetry, remediation activity and approval status from one portal.",
  },
];

const capabilities = [
  "Windows device health and live telemetry",
  "Evidence-first diagnosis and knowledge search",
  "Allowlisted self-healing actions",
  "Automatic, approval-required and admin-only tiers",
  "Patch and update visibility",
  "IT asset inventory and reporting",
  "Secure employee offboarding workflows",
  "Audit history for device commands and mutations",
];

const faqs = [
  {
    question: "What is AI IT support?",
    answer:
      "AI IT support combines endpoint data, operational knowledge and controlled automation to help diagnose and resolve IT issues. ASTRA gathers evidence first, then follows code-enforced approval and allowlist rules before any remediation can run.",
  },
  {
    question: "Does ASTRA replace an internal IT team?",
    answer:
      "No. ASTRA is designed to remove repetitive investigation and routine remediation work while technicians and administrators retain control of higher-risk decisions.",
  },
  {
    question: "Which devices are supported?",
    answer:
      "The ASTRA endpoint agent currently supports 64-bit Windows 10 and Windows 11 devices.",
  },
  {
    question: "Can Technomate provide on-site IT support?",
    answer:
      "Technomate provides managed IT and business hardware support from Dadri for organizations in Delhi NCR. Exact on-site coverage and response expectations are agreed during assessment.",
  },
  {
    question: "Can we evaluate ASTRA before buying?",
    answer:
      "Yes. Organizations can start a 14-day full-product trial without a credit card or book a guided fleet assessment and limited-device pilot.",
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

export default function AiItSupportIndiaPage() {
  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(faqSchema) }}
      />

      <section className="aurora grain relative -mt-16 overflow-hidden pb-20 pt-28 sm:pt-36">
        <Container>
          <div className="grid items-center gap-12 lg:grid-cols-[1.15fr_0.85fr]">
            <div>
              <Badge>
                <MapPin className="h-3.5 w-3.5 text-brand-500" /> India-based IT support
              </Badge>
              <h1 className="mt-5 text-4xl font-extrabold leading-tight tracking-tight sm:text-5xl lg:text-6xl">
                AI IT support for growing Windows teams in India
              </h1>
              <p className="mt-6 max-w-2xl text-lg leading-relaxed text-secondary-token">
                Combine ASTRA endpoint automation with Technomate managed IT support.
                Detect issues early, collect evidence automatically and resolve approved
                Windows problems without giving up human control.
              </p>
              <div className="mt-8 flex flex-wrap gap-3">
                <Button href={bookDemo.href} external={bookDemo.external}>
                  Book a fleet assessment <ArrowRight className="h-4 w-4" />
                </Button>
                <Button href={site.appUrl} variant="secondary" external>
                  Start the 14-day trial
                </Button>
              </div>
              <div className="mt-6 flex flex-wrap gap-x-6 gap-y-2 text-sm text-muted-token">
                <span className="flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-emerald-500" /> No credit card</span>
                <span className="flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-emerald-500" /> Windows 10 and 11</span>
                <span className="flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-emerald-500" /> Human approval controls</span>
              </div>
            </div>

            <aside className="rounded-3xl border border-token bg-surface p-7 shadow-xl">
              <div className="flex items-center gap-3">
                <div className="grid h-12 w-12 place-items-center rounded-xl bg-brand-500/10 text-brand-500">
                  <Sparkles className="h-6 w-6" />
                </div>
                <div>
                  <p className="font-bold">ASTRA AI System Administrator</p>
                  <p className="text-sm text-muted-token">Evidence, action, verification</p>
                </div>
              </div>
              <ol className="mt-7 space-y-4">
                {["Understand the issue", "Search enterprise knowledge", "Collect live endpoint evidence", "Apply the permitted action", "Verify and record the result"].map((step, index) => (
                  <li key={step} className="flex items-center gap-3">
                    <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-brand-600 text-xs font-bold text-white">{index + 1}</span>
                    <span className="text-sm text-secondary-token">{step}</span>
                  </li>
                ))}
              </ol>
              <Link href="/security/" className="mt-7 inline-flex items-center gap-2 text-sm font-semibold text-brand-500 hover:underline">
                Review ASTRA security controls <ArrowRight className="h-4 w-4" />
              </Link>
              <Link href="/blog/what-is-an-ai-system-administrator/" className="mt-3 flex items-center gap-2 text-sm font-semibold text-brand-500 hover:underline">
                Learn what an AI System Administrator does <ArrowRight className="h-4 w-4" />
              </Link>
            </aside>
          </div>
        </Container>
      </section>

      <Section>
        <Container>
          <div className="mx-auto max-w-2xl text-center">
            <p className="text-sm font-semibold uppercase tracking-wider text-brand-500">Built for lean IT teams</p>
            <h2 className="mt-3 text-3xl font-bold tracking-tight sm:text-4xl">Prevent tickets instead of only responding to them</h2>
            <p className="mt-4 text-secondary-token">ASTRA helps one-to-five-person IT teams manage growing Windows fleets without adding another dashboard that needs constant attention.</p>
          </div>
          <div className="mt-12 grid gap-6 md:grid-cols-3">
            {outcomes.map(({ icon: Icon, title, body }) => (
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
              <Badge><Laptop className="h-3.5 w-3.5 text-brand-500" /> Windows endpoint operations</Badge>
              <h2 className="mt-5 text-3xl font-bold tracking-tight sm:text-4xl">One partner from endpoint software to hands-on support</h2>
              <p className="mt-4 leading-relaxed text-secondary-token">
                Use ASTRA as software, work with Technomate on a guided rollout, or combine it with managed IT and business hardware support. The engagement can start with a limited device group and agreed success criteria.
              </p>
              <div className="mt-7 flex flex-wrap gap-3">
                <Button href="/astra/">Explore ASTRA</Button>
                <Button href="/windows-endpoint-automation/" variant="secondary">Endpoint automation</Button>
                <Button href="/contact/" variant="secondary">Discuss managed IT</Button>
                <Button href="/it-support-50-500-employees/" variant="secondary">For 50–500 employee teams</Button>
              </div>
            </div>
            <ul className="grid gap-3 sm:grid-cols-2">
              {capabilities.map((capability) => (
                <li key={capability} className="flex items-start gap-3 rounded-xl border border-token bg-app px-4 py-3">
                  <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-500" />
                  <span className="text-sm text-secondary-token">{capability}</span>
                </li>
              ))}
            </ul>
          </div>
        </Container>
      </Section>

      <Section>
        <Container>
          <div className="mx-auto max-w-3xl">
            <div className="text-center">
              <p className="text-sm font-semibold uppercase tracking-wider text-brand-500">Frequently asked questions</p>
              <h2 className="mt-3 text-3xl font-bold tracking-tight">AI IT support, without the guesswork</h2>
            </div>
            <div className="mt-10 space-y-4">
              {faqs.map((faq) => (
                <article key={faq.question} className="rounded-2xl border border-token bg-surface p-6">
                  <h3 className="font-bold">{faq.question}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-secondary-token">{faq.answer}</p>
                </article>
              ))}
            </div>
          </div>
        </Container>
      </Section>

      <Section className="pb-28 pt-0">
        <Container>
          <div className="rounded-3xl bg-gradient-to-br from-brand-600 to-violet-600 px-8 py-14 text-center text-white sm:px-14">
            <ShieldCheck className="mx-auto h-10 w-10" />
            <h2 className="mt-4 text-3xl font-bold">Start with a controlled device group</h2>
            <p className="mx-auto mt-4 max-w-xl text-white/85">Book a 30-minute assessment to review your Windows fleet, recurring tickets and the right pilot scope.</p>
            <a href={bookDemo.href} target={bookDemo.external ? "_blank" : undefined} rel={bookDemo.external ? "noopener" : undefined} className="mt-8 inline-flex items-center gap-2 rounded-xl bg-white px-6 py-3 text-sm font-semibold text-brand-700">
              Book the assessment <ArrowRight className="h-4 w-4" />
            </a>
          </div>
        </Container>
      </Section>
    </>
  );
}
