"use client";

import { motion } from "framer-motion";
import {
  ArrowRight,
  CheckCircle2,
  Clock,
  Globe,
  Lock,
  Mail,
  Network,
  ShieldCheck,
  Smartphone,
  Timer,
  UsersRound,
} from "lucide-react";

/* ----------------------------------------------------------------------------
 * Window chrome, matching the ASTRA panels so the two products read as one site.
 * Deliberately a local copy: visuals.tsx keeps its own private, and duplicating
 * twelve lines beats exporting an internal and coupling the two files.
 * ------------------------------------------------------------------------- */
function Chrome({ title, children, className = "" }: { title: string; children: React.ReactNode; className?: string }) {
  return (
    <div className={`overflow-hidden rounded-2xl border border-token bg-surface shadow-2xl ${className}`}>
      <div className="flex items-center gap-2 border-b border-token bg-surface-2 px-4 py-3">
        <span className="h-3 w-3 rounded-full bg-red-400/80" />
        <span className="h-3 w-3 rounded-full bg-amber-400/80" />
        <span className="h-3 w-3 rounded-full bg-emerald-400/80" />
        <span className="ml-3 text-xs font-medium text-muted-token">{title}</span>
      </div>
      <div className="p-4">{children}</div>
    </div>
  );
}

const row = (index: number) => ({
  initial: { opacity: 0, x: -14 },
  whileInView: { opacity: 1, x: 0 },
  viewport: { once: true },
  transition: { delay: index * 0.1 },
});

/* ----------------------------------------------------------------------------
 * What a member actually opens: the portals assigned to them, and nothing else.
 * ------------------------------------------------------------------------- */
export function VaultDashboard() {
  const portals = [
    { name: "Northwind Portal", host: "northwind.example.com", letter: "N" },
    { name: "Lakeside VMS", host: "lakeside.example.net", letter: "L" },
    { name: "Redwood Staffing", host: "redwood.example.org", letter: "R" },
  ];
  return (
    <Chrome title="My access — Secure Vault">
      <div className="grid grid-cols-12 gap-3">
        <div className="col-span-4 space-y-1.5 rounded-lg border border-token bg-surface-2 p-2.5">
          {[
            { label: "My access", count: 8, active: true },
            { label: "Groups", count: 3, active: false },
          ].map((item) => (
            <div
              key={item.label}
              className={`flex items-center justify-between rounded-md px-2 py-1.5 text-[11px] font-semibold ${item.active ? "bg-brand-500/10 text-brand-500" : "text-secondary-token"}`}
            >
              <span>{item.label}</span>
              <span className="rounded-full bg-surface px-1.5 py-0.5 text-[9px]">{item.count}</span>
            </div>
          ))}
          <div className="mt-3 rounded-md border border-emerald-500/25 bg-emerald-500/5 p-2">
            <div className="flex items-center gap-1.5 text-[10px] font-semibold text-emerald-500">
              <ShieldCheck className="h-3 w-3" /> Protected
            </div>
            <p className="mt-1 text-[9px] leading-snug text-muted-token">Credentials stay hidden and are filled for you.</p>
          </div>
        </div>
        <div className="col-span-8 space-y-2">
          {portals.map((portal, index) => (
            <motion.div key={portal.name} {...row(index)} className="flex items-center gap-2.5 rounded-lg border border-token bg-surface-2 px-3 py-2.5">
              <span className="grid h-8 w-8 flex-none place-items-center rounded-lg bg-brand-500/10 text-xs font-bold text-brand-500">{portal.letter}</span>
              <div className="min-w-0 flex-1">
                <div className="truncate text-xs font-semibold">{portal.name}</div>
                <div className="flex items-center gap-1 text-[10px] text-muted-token">
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" /> Credentials protected
                </div>
              </div>
              <span className="flex flex-none items-center gap-1 rounded-md bg-brand-600 px-2 py-1 text-[10px] font-bold text-white">
                Open <ArrowRight className="h-3 w-3" />
              </span>
            </motion.div>
          ))}
        </div>
      </div>
    </Chrome>
  );
}

/* ----------------------------------------------------------------------------
 * The differentiator, and the one thing a screenshot explains faster than prose:
 * the fields are filled and still unreadable.
 * ------------------------------------------------------------------------- */
export function MaskedFill() {
  return (
    <Chrome title="northwind.example.com — signing in">
      <div className="relative">
        <div className="space-y-3 rounded-lg border border-token bg-surface-2 p-4">
          {[
            { label: "Username", value: "recruiter@company.com" },
            { label: "Password", value: "Th3-P0rtal-Secret" },
          ].map((field) => (
            <div key={field.label}>
              <div className="text-[10px] font-semibold uppercase tracking-wide text-muted-token">{field.label}</div>
              <div className="mt-1 flex items-center gap-2 rounded-md border border-token bg-surface px-3 py-2">
                {/* The value is present and typed — it is simply not readable. */}
                <span className="select-none truncate text-xs text-primary-token blur-[3.5px]">{field.value}</span>
                <Lock className="ml-auto h-3 w-3 flex-none text-brand-500" />
              </div>
            </div>
          ))}
          <div className="rounded-md bg-brand-600 py-2 text-center text-[11px] font-bold text-white">Sign in</div>
        </div>
        <motion.div
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          transition={{ delay: 0.35 }}
          className="absolute inset-x-0 -top-1 mx-auto w-fit rounded-full border border-brand-500/30 bg-brand-500/10 px-3 py-1 text-[10px] font-bold tracking-wide text-brand-500 backdrop-blur"
        >
          SECURE SIGN-IN IN PROGRESS…
        </motion.div>
      </div>
      <div className="mt-3 grid gap-1.5">
        {["No reveal control anywhere", "Copying out is blocked", "The site's own eye toggle is reversed"].map((line) => (
          <div key={line} className="flex items-center gap-2 text-[10px] text-secondary-token">
            <CheckCircle2 className="h-3 w-3 flex-none text-brand-500" /> {line}
          </div>
        ))}
      </div>
    </Chrome>
  );
}

/* ----------------------------------------------------------------------------
 * Access as something granted, not sent.
 * ------------------------------------------------------------------------- */
export function GroupAccess() {
  const groups = [
    { name: "Recruiting team", members: 14, logins: 6 },
    { name: "Delivery team", members: 9, logins: 4 },
    { name: "Finance", members: 3, logins: 2 },
  ];
  return (
    <Chrome title="Groups & access — admin console">
      <div className="mb-3 grid grid-cols-12 gap-2 px-1 text-[11px] font-medium uppercase tracking-wide text-muted-token">
        <div className="col-span-6">Group</div>
        <div className="col-span-3">People</div>
        <div className="col-span-3 text-right">Portals</div>
      </div>
      <div className="space-y-2">
        {groups.map((group, index) => (
          <motion.div key={group.name} {...row(index)} className="grid grid-cols-12 items-center gap-2 rounded-lg border border-token bg-surface-2 px-3 py-2.5">
            <div className="col-span-6 flex items-center gap-2">
              <UsersRound className="h-4 w-4 flex-none text-brand-500" />
              <span className="truncate text-xs font-semibold">{group.name}</span>
            </div>
            <div className="col-span-3 text-[11px] text-secondary-token">{group.members} members</div>
            <div className="col-span-3 text-right text-[11px] text-secondary-token">{group.logins} logins</div>
          </motion.div>
        ))}
      </div>
      <div className="mt-3 flex items-center gap-2 rounded-lg border border-dashed border-brand-500/40 bg-brand-500/5 px-3 py-2.5 text-[11px] font-semibold text-brand-500">
        <UsersRound className="h-3.5 w-3.5" /> 4 selected users → Add to group
      </div>
    </Chrome>
  );
}

/* ----------------------------------------------------------------------------
 * The record a shared password can never produce.
 * ------------------------------------------------------------------------- */
export function LoginReport() {
  const rows = [
    { user: "a•••a@company.com", portal: "Northwind Portal", ip: "203.0.113.41", agent: "Chrome · Windows" },
    { user: "r•••t@company.com", portal: "Lakeside VMS", ip: "203.0.113.18", agent: "Edge · Windows" },
    { user: "m•••a@company.com", portal: "Redwood Staffing", ip: "198.51.100.7", agent: "Firefox · Windows" },
  ];
  return (
    <Chrome title="Login report — admin console">
      <div className="mb-3 grid grid-cols-12 gap-2 px-1 text-[11px] font-medium uppercase tracking-wide text-muted-token">
        <div className="col-span-4">User</div>
        <div className="col-span-3">Portal</div>
        <div className="col-span-5">From</div>
      </div>
      <div className="space-y-2">
        {rows.map((entry, index) => (
          <motion.div key={entry.user} {...row(index)} className="grid grid-cols-12 items-center gap-2 rounded-lg border border-token bg-surface-2 px-3 py-2.5">
            <div className="col-span-4 truncate text-[11px] font-semibold">{entry.user}</div>
            <div className="col-span-3 truncate text-[11px] text-secondary-token">{entry.portal}</div>
            <div className="col-span-5 text-right text-[10px] text-muted-token">
              <span className="font-mono">{entry.ip}</span> · {entry.agent}
            </div>
          </motion.div>
        ))}
      </div>
      <div className="mt-3 flex items-center justify-between rounded-lg border border-token bg-surface-2 px-3 py-2 text-[10px] text-muted-token">
        <span className="flex items-center gap-1.5"><Clock className="h-3 w-3 text-brand-500" /> Filter by person, portal and date</span>
        <span className="font-semibold text-brand-500">⇩ Export CSV</span>
      </div>
    </Chrome>
  );
}

/* ----------------------------------------------------------------------------
 * The two ways a one-time code reaches the portal without a person fetching it.
 * ------------------------------------------------------------------------- */
export function OneTimeCodes() {
  return (
    <Chrome title="One-time codes">
      <div className="grid gap-3 sm:grid-cols-2">
        <motion.div {...row(0)} className="rounded-lg border border-token bg-surface-2 p-3">
          <div className="flex items-center gap-2 text-[11px] font-semibold"><Smartphone className="h-3.5 w-3.5 text-brand-500" /> Authenticator</div>
          <div className="mt-3 text-center font-mono text-2xl font-bold tracking-[0.2em] text-brand-500">418 305</div>
          <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-surface">
            <motion.div
              className="h-full rounded-full bg-brand-500"
              initial={{ width: "100%" }}
              whileInView={{ width: "18%" }}
              viewport={{ once: true }}
              transition={{ duration: 2.4, ease: "linear" }}
            />
          </div>
          <p className="mt-2 text-[10px] leading-snug text-muted-token">Generated from the stored secret. Nobody reaches for a phone.</p>
        </motion.div>
        <motion.div {...row(1)} className="rounded-lg border border-token bg-surface-2 p-3">
          <div className="flex items-center gap-2 text-[11px] font-semibold"><Mail className="h-3.5 w-3.5 text-brand-500" /> Emailed code</div>
          <div className="mt-3 space-y-1.5">
            {["Watching the mailbox…", "Code received from the portal", "Entered and submitted"].map((step, index) => (
              <div key={step} className="flex items-center gap-2 text-[10px] text-secondary-token">
                <CheckCircle2 className={`h-3 w-3 flex-none ${index === 2 ? "text-emerald-500" : "text-brand-500"}`} /> {step}
              </div>
            ))}
          </div>
          <p className="mt-2 text-[10px] leading-snug text-muted-token">Read over IMAP from a mailbox you nominate.</p>
        </motion.div>
      </div>
    </Chrome>
  );
}

/* ----------------------------------------------------------------------------
 * The rules an administrator sets once and the platform enforces everywhere.
 * ------------------------------------------------------------------------- */
export function PolicyPanel() {
  const rules = [
    { icon: Network, label: "Block 0.0.0.0/0 outside office", tone: "text-red-500 bg-red-500/10", state: "Block" },
    { icon: Globe, label: "Allow 203.0.113.0/24 — head office", tone: "text-emerald-500 bg-emerald-500/10", state: "Allow" },
    { icon: ShieldCheck, label: "Require Microsoft SSO for everyone", tone: "text-brand-500 bg-brand-500/10", state: "On" },
    { icon: Timer, label: "Close an idle portal after 15 minutes", tone: "text-brand-500 bg-brand-500/10", state: "On" },
  ];
  return (
    <Chrome title="Security policies — admin console">
      <div className="space-y-2">
        {rules.map((rule, index) => (
          <motion.div key={rule.label} {...row(index)} className="flex items-center gap-2.5 rounded-lg border border-token bg-surface-2 px-3 py-2.5">
            <rule.icon className="h-4 w-4 flex-none text-brand-500" />
            <span className="min-w-0 flex-1 truncate text-[11px] font-medium">{rule.label}</span>
            <span className={`flex-none rounded-full px-2 py-0.5 text-[10px] font-semibold ${rule.tone}`}>{rule.state}</span>
          </motion.div>
        ))}
      </div>
      <p className="mt-3 text-[10px] leading-snug text-muted-token">
        Network rules apply to password sign-in, Microsoft SSO, the API and extension pairing alike.
      </p>
    </Chrome>
  );
}
