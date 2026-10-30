"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AnimatePresence, motion } from "framer-motion";
import {
  Headphones,
  Wrench,
  RefreshCw,
  Activity,
  DatabaseBackup,
  ShieldCheck,
  Network,
  UserPlus,
  Handshake,
  Check,
  ArrowRight,
  Bot,
  CircleCheck,
  Loader2,
  Laptop,
  Search,
  ClipboardList,
  Rocket,
  LifeBuoy,
} from "lucide-react";
import { Container, Section, Reveal, SectionHeading, Button } from "@/components/ui";
import { TiltCard } from "@/components/enhance";
import { quoteHref } from "@/lib/services";
import { cn } from "@/lib/utils";
import { ServiceHero, MiniFeatures, QuoteBand } from "../shared";

const included = [
  { icon: Headphones, title: "Helpdesk", desc: "Phone, email, WhatsApp and remote support for every user." },
  { icon: Wrench, title: "On-site support", desc: "An engineer at your office when a problem needs hands." },
  { icon: RefreshCw, title: "Patching & updates", desc: "Windows, Office and app updates tested and rolled out." },
  { icon: Activity, title: "24/7 monitoring", desc: "Disks, services, uptime and alerts — watched around the clock." },
  { icon: DatabaseBackup, title: "Backup & recovery", desc: "Scheduled backups of servers, files and Microsoft 365." },
  { icon: ShieldCheck, title: "Security", desc: "Antivirus/EDR, firewall management and security baselines." },
  { icon: Network, title: "Network & Wi-Fi", desc: "Switches, routers, Wi-Fi and internet links kept healthy." },
  { icon: UserPlus, title: "Joiners & leavers", desc: "Laptops, accounts and access set up — and removed — on time." },
  { icon: Handshake, title: "Vendor management", desc: "We deal with ISPs, OEM warranties and software vendors." },
];

const plans = [
  {
    name: "Essential",
    for: "Small offices that need a reliable helpdesk",
    features: ["Remote helpdesk (business hours)", "Patching & antivirus", "Device monitoring & alerts", "Monthly health report"],
  },
  {
    name: "Business",
    for: "Growing teams that want IT fully handled",
    features: ["Everything in Essential", "Scheduled on-site visits", "Backup & recovery", "Network & firewall management", "Joiner / leaver handling"],
    hot: true,
  },
  {
    name: "Enterprise",
    for: "Multi-site organisations with compliance needs",
    features: ["Everything in Business", "Extended-hours support", "Dedicated account manager", "Security reviews & audits", "SAVIO self-healing on every device"],
  },
];

const steps = [
  { icon: Search, title: "IT health check", desc: "We review every device, account and network — free." },
  { icon: ClipboardList, title: "Clear plan", desc: "A written scope, response targets and a fixed monthly fee." },
  { icon: Rocket, title: "Smooth onboarding", desc: "Monitoring and SAVIO agents deployed without disrupting work." },
  { icon: LifeBuoy, title: "Ongoing care", desc: "Helpdesk, maintenance and a monthly review with you." },
];

const tickets = [
  { user: "Priya · Accounts", issue: "Outlook not syncing", fix: "Profile repaired by SAVIO" },
  { user: "Rahul · Sales", issue: "Laptop disk 95% full", fix: "Temp files cleared automatically" },
  { user: "Front desk", issue: "Printer offline", fix: "Spooler restarted remotely" },
  { user: "Neha · HR", issue: "New joiner laptop", fix: "Set up & delivered" },
  { user: "Server room", issue: "Backup job warning", fix: "Re-run and verified" },
];

const addOns = ["Microsoft 365 management", "Firewall & VPN", "CCTV & access control", "Server management", "Cloud backup", "Hardware refresh"];

/** A support queue where tickets arrive and resolve themselves on a loop. */
function LiveDesk() {
  const [n, setN] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setN((x) => x + 1), 1800);
    return () => clearInterval(id);
  }, []);
  const visible = [0, 1, 2, 3].map((k) => ({ ...tickets[(n + k) % tickets.length], key: n + k, open: k === 0 }));
  return (
    <div className="glow overflow-hidden rounded-2xl border border-token bg-surface">
      <div className="flex items-center justify-between border-b border-token px-5 py-3">
        <span className="flex items-center gap-2 text-sm font-semibold">
          <span className="relative flex h-2 w-2">
            <span className="absolute h-full w-full animate-ping rounded-full bg-emerald-500 opacity-75" />
            <span className="relative h-2 w-2 rounded-full bg-emerald-500" />
          </span>
          Live support desk
        </span>
        <span className="text-xs text-muted-token">Sample activity</span>
      </div>
      <div className="space-y-2 p-4">
        <AnimatePresence initial={false} mode="popLayout">
          {visible.map((t) => (
            <motion.div
              key={t.key}
              layout
              initial={{ opacity: 0, y: -16, scale: 0.97 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, x: 40 }}
              transition={{ duration: 0.4 }}
              className="flex items-center gap-3 rounded-xl border border-token bg-app p-3"
            >
              <span className={cn("grid h-9 w-9 shrink-0 place-items-center rounded-lg", t.open ? "bg-amber-500/15 text-amber-500" : "bg-emerald-500/15 text-emerald-500")}>
                {t.open ? <Loader2 className="h-4 w-4 animate-spin" /> : <CircleCheck className="h-4 w-4" />}
              </span>
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-semibold">{t.issue}</div>
                <div className="truncate text-xs text-muted-token">
                  {t.user} · {t.open ? "Working on it…" : t.fix}
                </div>
              </div>
              <span className={cn("shrink-0 rounded-full px-2 py-0.5 text-[10px] font-bold", t.open ? "bg-amber-500/15 text-amber-500" : "bg-emerald-500/15 text-emerald-500")}>
                {t.open ? "Open" : "Resolved"}
              </span>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
      <div className="grid grid-cols-3 border-t border-token text-center">
        {[
          { v: "Remote", l: "Most fixes" },
          { v: "24/7", l: "Monitoring" },
          { v: "1", l: "Monthly fee" },
        ].map((s) => (
          <div key={s.l} className="py-3">
            <div className="text-sm font-bold gradient-text">{s.v}</div>
            <div className="text-[10px] text-muted-token">{s.l}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

/** Pick team size and add-ons; the quote request carries the choices. */
function PlanBuilder() {
  const [devices, setDevices] = useState(25);
  const [plan, setPlan] = useState("Business");
  const [extras, setExtras] = useState<string[]>(["Microsoft 365 management"]);
  const toggle = (x: string) => setExtras((e) => (e.includes(x) ? e.filter((y) => y !== x) : [...e, x]));
  const message = `Managed IT plan: ${plan}\nDevices / users: about ${devices}\nAdd-ons: ${extras.length ? extras.join(", ") : "none"}\n\nAnything else: `;

  return (
    <div className="rounded-3xl border border-token bg-surface p-7 sm:p-9">
      <div className="grid gap-8 lg:grid-cols-2">
        <div>
          <label className="block">
            <div className="flex items-baseline justify-between">
              <span className="text-sm font-semibold">How many devices / users?</span>
              <motion.span key={devices} initial={{ scale: 0.8 }} animate={{ scale: 1 }} className="text-2xl font-extrabold gradient-text">
                {devices}
                {devices >= 500 ? "+" : ""}
              </motion.span>
            </div>
            <input
              type="range"
              min={5}
              max={500}
              step={5}
              value={devices}
              onChange={(e) => setDevices(Number(e.target.value))}
              className="mt-4 w-full accent-[var(--accent)]"
            />
            <div className="mt-1 flex justify-between text-[10px] text-muted-token">
              <span>5</span>
              <span>500+</span>
            </div>
          </label>
          <div className="mt-7 text-sm font-semibold">Plan</div>
          <div className="mt-3 flex flex-wrap gap-2">
            {plans.map((p) => (
              <button
                key={p.name}
                type="button"
                onClick={() => setPlan(p.name)}
                className={cn(
                  "relative rounded-full px-4 py-2 text-sm font-semibold transition-colors",
                  plan === p.name ? "text-white" : "border border-token bg-app text-secondary-token hover:text-primary-token",
                )}
              >
                {plan === p.name && <motion.span layoutId="mit-plan" className="absolute inset-0 rounded-full bg-brand-600" />}
                <span className="relative">{p.name}</span>
              </button>
            ))}
          </div>
        </div>
        <div>
          <div className="text-sm font-semibold">Add-ons</div>
          <div className="mt-3 flex flex-wrap gap-2">
            {addOns.map((a) => {
              const on = extras.includes(a);
              return (
                <button
                  key={a}
                  type="button"
                  onClick={() => toggle(a)}
                  className={cn(
                    "inline-flex items-center gap-1.5 rounded-full border px-3.5 py-2 text-xs font-medium transition-colors",
                    on ? "border-brand-500 bg-brand-600 text-white" : "border-token bg-app text-secondary-token hover:border-brand-500/50",
                  )}
                >
                  {on && <Check className="h-3 w-3" />} {a}
                </button>
              );
            })}
          </div>
          <Link
            href={quoteHref("Managed IT Services", message)}
            className="mt-8 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-brand-600 px-5 py-3.5 text-sm font-semibold text-white shadow-lg shadow-brand-600/25 transition hover:-translate-y-0.5 hover:bg-brand-500"
          >
            Get my monthly quote <ArrowRight className="h-4 w-4" />
          </Link>
          <p className="mt-3 text-center text-xs text-muted-token">Fixed monthly fee based on your devices and plan — no surprise bills.</p>
        </div>
      </div>
    </div>
  );
}

export function ManagedItContent() {
  return (
    <>
      <ServiceHero
        icon={Headphones}
        crumb="Managed IT Services"
        badge="Managed IT services"
        title="Your whole IT department, [[for one monthly fee]]"
        sub="Helpdesk, on-site support, patching, monitoring, backups and security for every device and user — handled by our team and kept healthy by SAVIO, our AI System Administrator."
      >
        <Button href="#plan">
          Build your plan <ArrowRight className="h-4 w-4" />
        </Button>
        <Button href={quoteHref("Managed IT Services", "I'd like a free IT health check.")} variant="secondary">
          Free IT health check
        </Button>
      </ServiceHero>

      <Section>
        <Container>
          <div className="grid items-center gap-12 lg:grid-cols-2">
            <Reveal>
              <span className="text-sm font-semibold uppercase tracking-wider text-brand-500">Why managed IT</span>
              <h2 className="mt-3 text-3xl font-bold tracking-tight sm:text-4xl">Problems fixed before your team even notices</h2>
              <p className="mt-4 leading-relaxed text-secondary-token">
                Instead of calling someone when things break, we watch every device continuously. Routine issues — full disks,
                stuck services, failed updates — are fixed automatically by SAVIO, and our engineers handle the rest remotely or on-site.
              </p>
              <ul className="mt-6 space-y-3">
                {["One accountable team for all your IT", "Predictable monthly cost instead of surprise bills", "Every fix logged and reported to you", "Human approval for anything sensitive"].map((x, i) => (
                  <motion.li
                    key={x}
                    initial={{ opacity: 0, x: -14 }}
                    whileInView={{ opacity: 1, x: 0 }}
                    viewport={{ once: true }}
                    transition={{ delay: 0.1 + i * 0.08 }}
                    className="flex items-center gap-3 text-sm"
                  >
                    <span className="grid h-5 w-5 place-items-center rounded-full bg-brand-500/15 text-brand-500">
                      <Check className="h-3 w-3" />
                    </span>
                    {x}
                  </motion.li>
                ))}
              </ul>
            </Reveal>
            <Reveal delay={0.1}>
              <LiveDesk />
            </Reveal>
          </div>
        </Container>
      </Section>

      <Section className="bg-surface">
        <Container>
          <Reveal>
            <SectionHeading eyebrow="What's included" title="Everything IT, handled" subtitle="Pick a plan and we take responsibility for all of this." />
          </Reveal>
          <div className="mt-12 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {included.map((x, i) => (
              <Reveal key={x.title} delay={(i % 3) * 0.06}>
                <TiltCard className="h-full rounded-2xl">
                  <div className="ring-conic flex h-full gap-4 rounded-2xl border border-token bg-app p-6">
                    <span className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-gradient-to-br from-brand-600 to-cyan-500 text-white transition-transform duration-300 group-hover:-rotate-6 group-hover:scale-110">
                      <x.icon className="h-5 w-5" />
                    </span>
                    <div>
                      <h3 className="font-bold">{x.title}</h3>
                      <p className="mt-1 text-sm text-secondary-token">{x.desc}</p>
                    </div>
                  </div>
                </TiltCard>
              </Reveal>
            ))}
          </div>
        </Container>
      </Section>

      <Section>
        <Container>
          <Reveal>
            <SectionHeading eyebrow="Plans" title="Choose the level of care you need" subtitle="Every plan is a fixed monthly fee per device, quoted for your team." />
          </Reveal>
          <div className="mt-12 grid gap-6 lg:grid-cols-3">
            {plans.map((p, i) => (
              <Reveal key={p.name} delay={i * 0.1}>
                <motion.div
                  whileHover={{ y: -6 }}
                  className={cn(
                    "relative flex h-full flex-col rounded-3xl border p-8",
                    p.hot ? "border-transparent bg-gradient-to-br from-brand-700 via-brand-600 to-cyan-500 text-white shadow-2xl shadow-brand-600/25" : "border-token bg-surface",
                  )}
                >
                  {p.hot && <span className="absolute right-6 top-6 rounded-full bg-white/20 px-3 py-1 text-[11px] font-bold">Most popular</span>}
                  <h3 className="text-xl font-bold">{p.name}</h3>
                  <p className={cn("mt-1 text-sm", p.hot ? "text-white/80" : "text-secondary-token")}>{p.for}</p>
                  <ul className="mt-6 flex-1 space-y-2.5">
                    {p.features.map((f) => (
                      <li key={f} className="flex items-start gap-2 text-sm">
                        <Check className={cn("mt-0.5 h-4 w-4 shrink-0", p.hot ? "text-white" : "text-brand-500")} /> {f}
                      </li>
                    ))}
                  </ul>
                  <Link
                    href={quoteHref("Managed IT Services", `I'm interested in the ${p.name} managed IT plan.`)}
                    className={cn(
                      "mt-8 inline-flex items-center justify-center gap-2 rounded-xl px-5 py-3 text-sm font-semibold transition hover:-translate-y-0.5",
                      p.hot ? "bg-white text-brand-700" : "border border-token bg-app hover:border-brand-500/50",
                    )}
                  >
                    Get a quote <ArrowRight className="h-4 w-4" />
                  </Link>
                </motion.div>
              </Reveal>
            ))}
          </div>
        </Container>
      </Section>

      <Section id="plan" className="scroll-mt-20 bg-surface">
        <Container>
          <Reveal>
            <SectionHeading eyebrow="Plan builder" title="Tell us about your team" subtitle="Set your size and add-ons — we'll send a fixed monthly quote." />
          </Reveal>
          <Reveal delay={0.1} className="mt-12">
            <PlanBuilder />
          </Reveal>
        </Container>
      </Section>

      <Section>
        <Container>
          <Reveal>
            <SectionHeading eyebrow="Getting started" title="From first call to fully managed in days" />
          </Reveal>
          <div className="mt-12">
            <MiniFeatures items={steps} />
          </div>
          <Reveal delay={0.2}>
            <div className="mx-auto mt-14 flex max-w-3xl flex-col items-center gap-5 rounded-2xl border border-token bg-surface p-8 text-center sm:flex-row sm:text-left">
              <span className="grid h-14 w-14 shrink-0 place-items-center rounded-2xl bg-gradient-to-br from-brand-600 to-cyan-500 text-white">
                <Bot className="h-7 w-7" />
              </span>
              <div className="flex-1">
                <h3 className="font-bold">Powered by SAVIO</h3>
                <p className="mt-1 text-sm text-secondary-token">
                  Every managed device runs our AI System Administrator, which detects and fixes common problems on its own — with
                  approval tiers for anything sensitive.
                </p>
              </div>
              <Button href="/savio" variant="secondary" className="shrink-0">
                <Laptop className="h-4 w-4" /> See SAVIO
              </Button>
            </div>
          </Reveal>
        </Container>
      </Section>

      <QuoteBand
        title="Ready to hand over the IT headaches?"
        sub="Start with a free IT health check — we'll show you what needs attention and what it would cost to manage."
        interest="Managed IT Services"
        button="Book a free health check"
      />
    </>
  );
}
