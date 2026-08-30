import type { Metadata } from "next";
import Link from "next/link";
import {
  BadgeCheck,
  CheckCircle2,
  FileClock,
  KeyRound,
  LockKeyhole,
  Network,
  ShieldCheck,
  UserCheck,
} from "lucide-react";
import { Badge, Button, Container, Section } from "@/components/ui";
import { bookDemo, site } from "@/lib/site";

export const metadata: Metadata = {
  title: "Security & Trust",
  description:
    "How ASTRA protects Windows endpoint operations with code-enforced approvals, allowlisted actions, least privilege, encrypted credentials and auditable activity.",
  alternates: { canonical: "/security/" },
};

const controls = [
  {
    icon: UserCheck,
    title: "Code-enforced approval tiers",
    body: "Every remediation is classified as automatic, approval-required or admin-only. The backend enforces who may approve an action; the AI cannot promote its own permissions.",
  },
  {
    icon: BadgeCheck,
    title: "Independent action allowlists",
    body: "The backend validates requested remediations and the Windows agent maintains its own hardcoded allowlist. Unknown action identifiers are refused at the endpoint.",
  },
  {
    icon: KeyRound,
    title: "Role-based access",
    body: "Organization-scoped API access and role checks separate end users, technicians, administrators and platform operators. Sensitive mutations require the appropriate role.",
  },
  {
    icon: FileClock,
    title: "Auditable operations",
    body: "Mutations and commands sent to devices are recorded with organization, actor and action context so authorized teams can review what happened.",
  },
  {
    icon: Network,
    title: "Outbound-only agent connectivity",
    body: "The Windows agent initiates outbound HTTPS connections on port 443. Customers do not need to expose inbound device ports for ASTRA.",
  },
  {
    icon: LockKeyhole,
    title: "Protected credentials",
    body: "Device credentials are stored with Windows DPAPI using LocalMachine scope. Supported integration credentials are encrypted before database storage.",
  },
];

const dataPractices = [
  "Short-lived access tokens with single-use rotating refresh tokens",
  "HTTPS for portal, API and agent communication",
  "Organization-scoped access to telemetry and audit records",
  "Raw telemetry retention configurable by deployment; production defaults are documented and reviewed",
  "No arbitrary PowerShell or unrestricted command execution path",
  "Post-remediation status reporting so teams can confirm the outcome",
];

export default function SecurityPage() {
  return (
    <>
      <section className="aurora grain relative -mt-16 overflow-hidden pb-16 pt-28 sm:pt-36">
        <Container>
          <div className="max-w-3xl">
            <Badge>
              <ShieldCheck className="h-3.5 w-3.5 text-brand-500" /> Security &amp; trust
            </Badge>
            <h1 className="mt-5 text-4xl font-extrabold leading-tight tracking-tight sm:text-5xl">
              Automation with boundaries your IT team controls
            </h1>
            <p className="mt-6 max-w-2xl text-lg leading-relaxed text-secondary-token">
              ASTRA gathers evidence before acting, limits execution to known remediations,
              and keeps sensitive decisions with authorized people. These controls are
              implemented in the platform and Windows agent, not left to prompt instructions.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Button href={bookDemo.href} external={bookDemo.external}>Review security in a demo</Button>
              <Button href={`mailto:${site.contact.security}`} variant="secondary" external>
                Contact security
              </Button>
            </div>
          </div>
        </Container>
      </section>

      <Section>
        <Container>
          <div className="mx-auto max-w-2xl text-center">
            <p className="text-sm font-semibold uppercase tracking-wider text-brand-500">Core controls</p>
            <h2 className="mt-3 text-3xl font-bold tracking-tight sm:text-4xl">Defense in depth from API to endpoint</h2>
            <p className="mt-4 text-secondary-token">A remediation must pass policy checks in the cloud and execution checks on the device.</p>
          </div>
          <div className="mt-12 grid gap-5 md:grid-cols-2 lg:grid-cols-3">
            {controls.map(({ icon: Icon, title, body }) => (
              <article key={title} className="rounded-2xl border border-token bg-surface p-6">
                <div className="grid h-11 w-11 place-items-center rounded-xl bg-brand-500/10 text-brand-500"><Icon className="h-5 w-5" /></div>
                <h3 className="mt-4 font-bold">{title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-secondary-token">{body}</p>
              </article>
            ))}
          </div>
        </Container>
      </Section>

      <Section className="bg-surface">
        <Container>
          <div className="grid gap-10 lg:grid-cols-2 lg:items-center">
            <div>
              <p className="text-sm font-semibold uppercase tracking-wider text-brand-500">Data handling</p>
              <h2 className="mt-3 text-3xl font-bold tracking-tight">Clear operational safeguards</h2>
              <p className="mt-4 leading-relaxed text-secondary-token">
                ASTRA is designed to minimize exposed interfaces and keep customer data separated by organization. Exact retention and deployment requirements can be reviewed during a pilot.
              </p>
            </div>
            <ul className="space-y-3">
              {dataPractices.map((practice) => (
                <li key={practice} className="flex items-start gap-3 rounded-xl border border-token bg-app px-4 py-3">
                  <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-500" />
                  <span className="text-sm text-secondary-token">{practice}</span>
                </li>
              ))}
            </ul>
          </div>
        </Container>
      </Section>

      <Section className="pb-28">
        <Container>
          <div className="rounded-3xl border border-token bg-surface p-8 text-center sm:p-12">
            <h2 className="text-2xl font-bold sm:text-3xl">Need a security review before a pilot?</h2>
            <p className="mx-auto mt-3 max-w-xl text-secondary-token">We can walk your technical team through the action catalogue, approval flow, network requirements and audit trail.</p>
            <div className="mt-7 flex flex-wrap justify-center gap-3">
              <Button href={bookDemo.href} external={bookDemo.external}>Book a security walkthrough</Button>
              <Link href="/privacy/" className="inline-flex items-center rounded-xl px-5 py-3 text-sm font-semibold text-brand-500 hover:underline">Read the Privacy Policy</Link>
            </div>
          </div>
        </Container>
      </Section>
    </>
  );
}
