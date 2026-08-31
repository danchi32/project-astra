import type { Metadata } from "next";
import Link from "next/link";
import {
  ArrowRight, BadgeCheck, BriefcaseBusiness, CheckCircle2, Globe2,
  Laptop, LockKeyhole, MapPin, ShieldCheck, UserRoundCog, Wifi,
} from "lucide-react";
import { Badge, Button, Container, Section } from "@/components/ui";
import { bookDemo, site } from "@/lib/site";

export const metadata: Metadata = {
  title: "Remote Workforce IT Support Software India",
  description:
    "ASTRA helps remote and hybrid Indian startups monitor distributed Windows endpoints, investigate issues and run approved fixes without building a large IT support team.",
  keywords: [
    "remote workforce IT support India",
    "IT support for remote employees",
    "startup IT support India",
    "hybrid workforce endpoint management",
    "remote Windows support software",
    "distributed team IT automation",
  ],
  alternates: { canonical: "/remote-workforce-it-support-india/" },
  openGraph: {
    title: "Remote Workforce IT Support for Indian Startups",
    description:
      "Give a lean operations or IT team visibility and controlled support across distributed Windows devices.",
    url: "/remote-workforce-it-support-india/",
    type: "website",
  },
};

const problems = [
  {
    icon: MapPin,
    title: "Devices are spread across cities",
    body: "A laptop issue cannot always wait for an office visit, courier cycle or long screen-sharing session.",
  },
  {
    icon: UserRoundCog,
    title: "IT ownership is shared",
    body: "Founders, operations and people teams often coordinate support while an internal IT function is still small.",
  },
  {
    icon: Wifi,
    title: "Remote evidence is incomplete",
    body: "Without current device context, routine Windows problems become repeated questions and trial-and-error fixes.",
  },
];

const fit = [
  "20-150 employees in India",
  "Remote-first or hybrid operating model",
  "A meaningful Windows 10 or Windows 11 device group",
  "Employees distributed across multiple locations",
  "No dedicated IT team or a lean IT/operations function",
  "Named approver for sensitive endpoint actions",
];

const boundaries = [
  "Evidence is collected before a remediation is proposed",
  "Only allowlisted actions can reach an endpoint",
  "Sensitive actions remain approval-required or administrator-only",
  "Every attempted action keeps an attributable audit record",
  "Verification records resolved, failed and inconclusive outcomes",
  "ASTRA supports people responsible for IT; it does not remove accountability",
];

const faqs = [
  {
    question: "Is ASTRA suitable for a startup without a dedicated IT team?",
    answer:
      "It can be a fit when a named founder, operations lead or technical owner is accountable for device policy and approvals. ASTRA can standardize evidence gathering and permitted repeat work, but the organization still needs a responsible decision-maker.",
  },
  {
    question: "Can ASTRA support employees working from different Indian cities?",
    answer:
      "Yes. ASTRA is cloud-delivered software for supported, internet-connected Windows endpoints. A pilot should confirm connectivity, deployment and policy requirements for the actual remote device group.",
  },
  {
    question: "Does ASTRA work with employee-owned devices?",
    answer:
      "BYOD should be evaluated separately. Enrollment requires clear organizational authorization, employee notice and an agreed boundary between company support data and personal use. A company-managed pilot group is the safer starting point.",
  },
  {
    question: "Will ASTRA automatically run every fix?",
    answer:
      "No. Actions are separated into automatic, approval-required and administrator-only tiers. The model cannot lower a sensitive action into a less restrictive tier.",
  },
  {
    question: "How should a remote startup evaluate ASTRA?",
    answer:
      "Start with up to 10 representative company-managed Windows devices, three to five recurring issues, named approvers and written success criteria. The guided pilot is free for 14 days and has no automatic paid conversion.",
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
      url: "https://technomateai.com/remote-workforce-it-support-india/",
      description: metadata.description,
      audience: {
        "@type": "BusinessAudience",
        audienceType: "Remote and hybrid startups and small businesses",
        geographicArea: { "@type": "Country", name: "India" },
      },
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

export default function RemoteWorkforceItSupportIndiaPage() {
  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }} />

      <section className="aurora grain relative -mt-16 overflow-hidden pb-20 pt-28 sm:pt-36">
        <Container>
          <div className="grid items-center gap-12 lg:grid-cols-[1.15fr_0.85fr]">
            <div>
              <Badge><Globe2 className="h-3.5 w-3.5 text-brand-500" /> For remote and hybrid teams across India</Badge>
              <h1 className="mt-5 text-4xl font-extrabold leading-tight tracking-tight sm:text-5xl lg:text-6xl">
                Support distributed Windows teams without building a large IT desk
              </h1>
              <p className="mt-6 max-w-3xl text-lg leading-relaxed text-secondary-token">
                ASTRA helps startup operations and lean IT teams see endpoint health, collect evidence and run approved Windows fixes across remote locations while people retain control of sensitive decisions.
              </p>
              <div className="mt-8 flex flex-wrap gap-3">
                <Button href={bookDemo.href} external={bookDemo.external}>Plan a free 10-device pilot <ArrowRight className="h-4 w-4" /></Button>
                <Button href={site.appUrl} variant="secondary" external>Start the 14-day trial</Button>
              </div>
              <div className="mt-7 flex flex-wrap gap-x-6 gap-y-2 text-sm text-muted-token">
                <span className="flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-emerald-500" /> India-wide software delivery</span>
                <span className="flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-emerald-500" /> No credit card</span>
                <span className="flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-emerald-500" /> Human approval controls</span>
              </div>
            </div>

            <aside className="rounded-3xl border border-token bg-surface p-7 shadow-xl">
              <p className="text-sm font-semibold uppercase tracking-wider text-brand-500">A practical first fit</p>
              <h2 className="mt-3 text-2xl font-bold">Remote startup pilot profile</h2>
              <ul className="mt-6 space-y-3">
                {fit.map((item) => (
                  <li key={item} className="flex items-start gap-3">
                    <BadgeCheck className="mt-0.5 h-5 w-5 shrink-0 text-emerald-500" />
                    <span className="text-sm text-secondary-token">{item}</span>
                  </li>
                ))}
              </ul>
              <Link href="/pilot/" className="mt-7 inline-flex items-center gap-2 text-sm font-semibold text-brand-500 hover:underline">
                Review the pilot terms <ArrowRight className="h-4 w-4" />
              </Link>
            </aside>
          </div>
        </Container>
      </section>

      <Section>
        <Container>
          <div className="mx-auto max-w-2xl text-center">
            <p className="text-sm font-semibold uppercase tracking-wider text-brand-500">The distributed support gap</p>
            <h2 className="mt-3 text-3xl font-bold tracking-tight sm:text-4xl">Remote work changes where IT problems happen</h2>
          </div>
          <div className="mt-12 grid gap-6 md:grid-cols-3">
            {problems.map(({ icon: Icon, title, body }) => (
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
              <Badge><ShieldCheck className="h-3.5 w-3.5 text-brand-500" /> Control stays with your team</Badge>
              <h2 className="mt-5 text-3xl font-bold tracking-tight sm:text-4xl">Standardize routine support without creating unattended access</h2>
              <p className="mt-4 leading-relaxed text-secondary-token">
                ASTRA follows an evidence-first workflow and code-enforced remediation tiers. Start with company-managed devices and a small action catalogue before considering broader deployment.
              </p>
              <p className="mt-3 text-sm leading-relaxed text-secondary-token">
                New to the category? Read what an{" "}
                <Link href="/blog/what-is-an-ai-system-administrator/" className="font-semibold text-brand-500 hover:underline">
                  AI System Administrator
                </Link>{" "}
                does before planning the pilot.
              </p>
              <div className="mt-7 flex flex-wrap gap-3">
                <Button href="/security/">Review security controls</Button>
                <Button href="/windows-endpoint-automation/" variant="secondary">Explore endpoint automation</Button>
              </div>
            </div>
            <ul className="grid gap-3">
              {boundaries.map((item) => (
                <li key={item} className="flex items-start gap-3 rounded-xl border border-token bg-app px-4 py-3">
                  <LockKeyhole className="mt-0.5 h-5 w-5 shrink-0 text-brand-500" />
                  <span className="text-sm text-secondary-token">{item}</span>
                </li>
              ))}
            </ul>
          </div>
        </Container>
      </Section>

      <Section>
        <Container>
          <div className="grid gap-10 lg:grid-cols-[0.85fr_1.15fr] lg:items-center">
            <div>
              <Badge><BriefcaseBusiness className="h-3.5 w-3.5 text-brand-500" /> Designed for a lean operating team</Badge>
              <h2 className="mt-5 text-3xl font-bold tracking-tight">Bring one recurring remote Windows problem</h2>
              <p className="mt-4 leading-relaxed text-secondary-token">
                We will map the device evidence, permitted action, responsible approver and verification step. The pilot begins only after the scope is agreed and the first approved endpoint reports successfully.
              </p>
            </div>
            <div className="rounded-2xl border border-token bg-surface p-7">
              <div className="flex items-center gap-3"><Laptop className="h-6 w-6 text-brand-500" /><h3 className="text-xl font-bold">Free guided pilot</h3></div>
              <ol className="mt-6 space-y-4">
                {["Choose up to 10 company-managed Windows devices", "Select three to five recurring support issues", "Name approvers and action boundaries", "Review evidence, outcomes and exceptions after 14 days"].map((step, index) => (
                  <li key={step} className="flex items-start gap-3">
                    <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-brand-600 text-xs font-bold text-white">{index + 1}</span>
                    <span className="text-sm text-secondary-token">{step}</span>
                  </li>
                ))}
              </ol>
            </div>
          </div>
        </Container>
      </Section>

      <Section className="bg-surface">
        <Container>
          <div className="mx-auto max-w-3xl">
            <div className="text-center">
              <p className="text-sm font-semibold uppercase tracking-wider text-brand-500">Frequently asked questions</p>
              <h2 className="mt-3 text-3xl font-bold tracking-tight">Remote endpoint support with clear boundaries</h2>
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
            <Globe2 className="mx-auto h-10 w-10" />
            <h2 className="mt-4 text-3xl font-bold">Test ASTRA with a distributed device group</h2>
            <p className="mx-auto mt-4 max-w-xl text-white/85">Bring your Windows device count, team locations and most common remote support issue to a 30-minute pilot-planning session.</p>
            <a href={bookDemo.href} target={bookDemo.external ? "_blank" : undefined} rel={bookDemo.external ? "noopener" : undefined} className="mt-8 inline-flex items-center gap-2 rounded-xl bg-white px-6 py-3 text-sm font-semibold text-brand-700">
              Plan the free pilot <ArrowRight className="h-4 w-4" />
            </a>
          </div>
        </Container>
      </Section>
    </>
  );
}
