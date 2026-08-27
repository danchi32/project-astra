import type { Metadata } from "next";
import { Container, Section, Badge } from "@/components/ui";
import { LeadMagnetForm } from "@/components/LeadMagnetForm";
import { FileCheck2, ShieldCheck, Clock, ListChecks } from "lucide-react";

const ASSET_URL = "/resources/secure-offboarding-checklist.pdf";

export const metadata: Metadata = {
  title: "Free Secure Employee Offboarding Checklist (PDF)",
  description:
    "Download the free one-page IT checklist to lock down a departing employee's access — accounts, sessions, devices and data — before anything walks out the door.",
  alternates: { canonical: "/resources/offboarding-checklist/" },
};

const inside = [
  { icon: Clock, title: "The first-hour actions", desc: "What to do the moment someone leaves — disable the account and end the active session." },
  { icon: ListChecks, title: "Access, device & data steps", desc: "Revoke SaaS access, secure the device, rotate shared secrets, reassign files." },
  { icon: ShieldCheck, title: "Compliance & audit", desc: "Log every action and confirm completion so nothing slips through." },
];

export default function OffboardingChecklistPage() {
  return (
    <Section className="aurora grain relative -mt-16 pt-28 sm:pt-36">
      <Container>
        <div className="grid items-start gap-10 lg:grid-cols-2 lg:gap-16">
          {/* Pitch */}
          <div>
            <Badge>
              <FileCheck2 className="h-3.5 w-3.5 text-brand-500" /> Free checklist · PDF
            </Badge>
            <h1 className="mt-5 text-3xl font-bold tracking-tight sm:text-4xl">
              The Secure Employee Offboarding Checklist
            </h1>
            <p className="mt-4 text-base leading-relaxed text-secondary-token sm:text-lg">
              The riskiest window in your security is the hour after someone
              leaves. This one-page checklist walks your IT team through locking
              down a leaver&apos;s access — before data can walk out the door.
            </p>

            <div className="mt-8 space-y-4">
              {inside.map((item) => {
                const Icon = item.icon;
                return (
                  <div key={item.title} className="flex gap-3.5">
                    <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-brand-500/10 text-brand-500">
                      <Icon className="h-5 w-5" />
                    </span>
                    <div>
                      <p className="text-sm font-semibold">{item.title}</p>
                      <p className="mt-0.5 text-sm leading-relaxed text-secondary-token">
                        {item.desc}
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>

            <p className="mt-8 rounded-xl border border-token bg-surface px-4 py-3 text-sm text-secondary-token">
              Built by <strong className="text-primary-token">Technomate</strong>,
              makers of <strong className="text-primary-token">ASTRA</strong> — the
              AI System Administrator that turns this whole checklist into one click.
            </p>
          </div>

          {/* Capture */}
          <div className="lg:sticky lg:top-28">
            <LeadMagnetForm
              assetUrl={ASSET_URL}
              assetName="Secure Offboarding Checklist"
              leadLabel="offboarding_checklist"
            />
          </div>
        </div>
      </Container>
    </Section>
  );
}
