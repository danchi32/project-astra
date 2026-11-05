import type { Metadata } from "next";
import Link from "next/link";
import { Calculator } from "lucide-react";
import { Container, Section, Badge } from "@/components/ui";
import { TicketCostCalculator } from "@/components/TicketCostCalculator";
import { site } from "@/lib/site";

export const metadata: Metadata = {
  title: "IT Support Ticket Cost Calculator (Free, in ₹)",
  description:
    "Work out what IT support tickets really cost your business each year: IT staff time plus employee downtime, in rupees. Free calculator for teams with 25–500 Windows PCs.",
  keywords: [
    "IT ticket cost calculator",
    "cost per ticket IT support",
    "helpdesk cost calculator",
    "IT downtime cost calculator India",
    "IT support cost per employee",
  ],
  alternates: { canonical: "/resources/it-ticket-cost-calculator/" },
};

const faqs = [
  {
    q: "How is the cost per ticket calculated?",
    a: "It adds two things: the IT staff time spent on each ticket, multiplied by IT's hourly cost, and the time the employee loses while the problem is open, multiplied by their hourly cost. Most teams only count the first half, which is why tickets look cheaper than they are.",
  },
  {
    q: "How do I find my hourly cost?",
    a: "Take the monthly cost to the company (CTC) and divide it by about 160 working hours. For example, ₹80,000 a month is roughly ₹500 an hour.",
  },
  {
    q: "What counts as a repetitive ticket?",
    a: "The same few problems that come back every week: a slow PC, a stuck printer queue, Outlook not responding, no sound in a meeting, websites not loading. Pull the last 90 days of tickets and group them by cause to get your own percentage.",
  },
  {
    q: "Is any of my data stored?",
    a: "No. The calculation runs in your browser and nothing you type is sent anywhere.",
  },
];

const guides = [
  { href: "/blog/windows-pc-slow-disk-full-fix/", label: "Windows PC slow or disk full" },
  { href: "/blog/printer-not-printing-fix-print-spooler/", label: "Printer not printing" },
  { href: "/blog/outlook-not-responding-fix/", label: "Outlook not responding" },
  { href: "/blog/internet-not-working-windows-flush-dns-reset-network/", label: "Internet not working on one PC" },
  { href: "/blog/no-sound-microphone-not-working-windows/", label: "No sound or microphone not working" },
  { href: "/blog/reset-windows-update-components/", label: "Windows Update stuck or failing" },
];

export default function TicketCostCalculatorPage() {
  const base = `https://${site.domain}`;
  const ld = [
    {
      "@context": "https://schema.org",
      "@type": "WebApplication",
      name: "IT Support Ticket Cost Calculator",
      url: `${base}/resources/it-ticket-cost-calculator/`,
      applicationCategory: "BusinessApplication",
      operatingSystem: "Any",
      offers: { "@type": "Offer", price: "0", priceCurrency: "INR" },
      publisher: { "@id": `${base}/#organization` },
    },
    {
      "@context": "https://schema.org",
      "@type": "FAQPage",
      mainEntity: faqs.map((f) => ({
        "@type": "Question",
        name: f.q,
        acceptedAnswer: { "@type": "Answer", text: f.a },
      })),
    },
  ];

  return (
    <Section className="aurora grain relative -mt-16 pt-28 sm:pt-36">
      {ld.map((d, i) => (
        <script key={i} type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(d) }} />
      ))}
      <Container>
        <div className="max-w-3xl">
          <Badge>
            <Calculator className="h-3.5 w-3.5 text-brand-500" /> Free calculator
          </Badge>
          <h1 className="mt-5 text-3xl font-bold tracking-tight sm:text-4xl">
            What do your IT tickets really cost?
          </h1>
          <p className="mt-4 text-base leading-relaxed text-secondary-token sm:text-lg">
            Every ticket costs twice: once in IT&apos;s time, and again in the time an employee
            can&apos;t work. Enter your own numbers to see the yearly cost in rupees, and how much
            of it goes on the same problems coming back.
          </p>
        </div>

        <div className="mt-10">
          <TicketCostCalculator />
        </div>

        <div className="mt-16 grid gap-12 lg:grid-cols-2">
          <div>
            <h2 className="text-2xl font-bold tracking-tight">Common questions</h2>
            <div className="mt-6 space-y-6">
              {faqs.map((f) => (
                <div key={f.q}>
                  <h3 className="text-base font-semibold">{f.q}</h3>
                  <p className="mt-1.5 text-sm leading-relaxed text-secondary-token">{f.a}</p>
                </div>
              ))}
            </div>
          </div>

          <div>
            <h2 className="text-2xl font-bold tracking-tight">Fix the repetitive ones faster</h2>
            <p className="mt-3 text-sm leading-relaxed text-secondary-token">
              Step-by-step guides for the tickets that come back most often:
            </p>
            <ul className="mt-4 space-y-2">
              {guides.map((g) => (
                <li key={g.href}>
                  <Link href={g.href} className="text-sm font-medium text-brand-500 hover:underline">
                    {g.label}
                  </Link>
                </li>
              ))}
            </ul>
            <p className="mt-6 rounded-xl border border-token bg-surface px-4 py-3 text-sm text-secondary-token">
              Built by <strong className="text-primary-token">Technomate</strong>, makers of{" "}
              <Link href="/savio/" className="font-semibold text-primary-token hover:text-brand-500">
                SAVIO
              </Link>{" "}
              — the AI System Administrator that fixes routine Windows tickets on its own, with
              sensitive actions kept behind IT approval.
            </p>
          </div>
        </div>
      </Container>
    </Section>
  );
}
