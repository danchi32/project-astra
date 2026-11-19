"use client";
import { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Download } from "lucide-react";
import { getCompliancePack, type CompliancePack } from "@/lib/api/reports";
import { isUpgradeRequired, UpgradeRequired, requiredFeature } from "@/components/upgrade-required";
import { apiErrorMessage } from "@/lib/utils";

// Phase 3b · J4 — the compliance pack: the evidence an auditor, insurer or client asks for, from
// SAVIO's own records, printed with the browser's print-to-PDF. The admin picks which parts go in.
// Evidence, never a certificate. Admin only: it names staff and PCs.

type Part = "security" | "access" | "changes" | "data_protection";
const PARTS: { key: Part; label: string }[] = [
  { key: "security", label: "Endpoint security" }, { key: "access", label: "Who can do what" },
  { key: "changes", label: "Record of changes" }, { key: "data_protection", label: "Data protection (DPDP)" },
];
const STATUS: Record<string, string> = { compliant: "Healthy", at_risk: "At risk", non_compliant: "Needs attention", unknown: "Not known" };
const ROLE: Record<string, string> = { admin: "Admin", technician: "Technician", user: "User" };

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-xl p-5 space-y-3 break-inside-avoid" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
      <h2 className="text-sm font-semibold uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>{title}</h2>
      {children}
    </section>
  );
}

function Table({ head, rows }: { head: string[]; rows: (string | number)[][] }) {
  return (
    <table className="w-full text-xs">
      <thead><tr>{head.map((h) => <th key={h} className="text-left py-1 pr-3 uppercase" style={{ color: "var(--text-secondary)" }}>{h}</th>)}</tr></thead>
      <tbody>{rows.map((r, n) => (
        <tr key={n} className="align-top" style={{ color: "var(--text-primary)", borderTop: "1px solid var(--border)" }}>
          {r.map((c, i) => <td key={i} className="py-1 pr-3">{c}</td>)}
        </tr>))}
      </tbody>
    </table>
  );
}

function Pack({ p, parts }: { p: CompliancePack; parts: Set<Part> }) {
  const s = p.security;
  const dp = p.data_protection;
  const text = { color: "var(--text-primary)" };
  return (
    <>
      {parts.has("security") && (
        <Section title="Endpoint security">
          <p className="text-sm" style={text}>
            {s.devices} computers · security score {s.security_score ?? "not known yet"}{s.security_score != null && "%"} ·
            {" "}{s.compliant} healthy, {s.at_risk} at risk, {s.non_compliant} need attention, {s.unknown} not known.
            {" "}USB storage blocked on {s.usb.blocked}, allowed on {s.usb.allowed}, not reported on {s.usb.unknown}.
          </p>
          <Table head={["Check", "Pass", "Fail", "Not known"]} rows={s.checks.map((c) => [c.label, c.passed, c.failed, c.unknown])} />
          <Table head={["Computer", "Score", "State", "Failing"]}
            rows={s.per_device.map((d) => [d.hostname, d.score, STATUS[d.status] ?? d.status, d.failed.join(", ") || "—"])} />
        </Section>
      )}
      {parts.has("access") && (
        <Section title="Who can do what">
          <p className="text-sm" style={text}>
            {p.access.by_role.admin} admin(s), {p.access.by_role.technician} technician(s), {p.access.by_role.user} user(s) active;
            {" "}{p.access.inactive} account(s) switched off. Every change and every command sent to a computer is in the audit log.
          </p>
          <Table head={["Name", "Role"]} rows={p.access.staff.map((u) => [u.name, ROLE[u.role] ?? u.role])} />
        </Section>
      )}
      {parts.has("changes") && (
        <Section title="Record of changes">
          <p className="text-sm" style={text}>{p.changes.total.toLocaleString()} recorded changes and actions in the period. The most frequent:</p>
          <Table head={["Action", "Times"]} rows={p.changes.by_action.map((c) => [c.action, c.count])} />
        </Section>
      )}
      {parts.has("data_protection") && dp && (
        <Section title="Data protection (DPDP)">
          <p className="text-sm" style={text}>
            Readiness {dp.score}% ({dp.done} of {dp.total} in place). Privacy and breach contact:{" "}
            {dp.contact.name ? `${dp.contact.name} (${dp.contact.email})` : "not named yet"}.
          </p>
          <Table head={["", "Safeguard", "Evidence"]} rows={dp.items.map((i) => [i.status === "done" ? "✓" : "○", i.title, i.detail])} />
          {dp.retention.length > 0 && (
            <Table head={["Computer", "Folder", "Files unchanged 2+ years"]} rows={dp.retention.map((r) => [r.hostname, r.path, r.old])} />
          )}
          <Table head={["Breach record", "Found", "State", "Steps settled"]}
            rows={dp.breaches.length ? dp.breaches.map((b) => [b.title, new Date(b.found_at).toLocaleString(), b.status === "open" ? "Open" : "Closed", `${b.steps_settled} of 6`])
              : [["None in the period", "", "", ""]]} />
        </Section>
      )}
    </>
  );
}

export default function CompliancePackPage() {
  const [days, setDays] = useState<30 | 90>(90);
  const [parts, setParts] = useState<Set<Part>>(new Set(PARTS.map((x) => x.key)));
  const { data: p, error, isLoading } = useQuery({ queryKey: ["compliance-pack", days], queryFn: () => getCompliancePack(days), retry: false });
  const muted = { color: "var(--text-secondary)" };
  const panel = { background: "var(--surface)", border: "1px solid var(--border)" };
  const forbidden = (error as { response?: { status?: number } } | null)?.response?.status === 403;

  if (isUpgradeRequired(error)) return <UpgradeRequired feature={requiredFeature(error)} />;
  if (forbidden) return <p className="text-sm" style={muted}>Only an admin can make a compliance pack: it names staff and computers.</p>;

  return (
    <div className="space-y-5 max-w-4xl mx-auto print:max-w-none">
      <div className="flex flex-wrap items-center justify-between gap-3 print:hidden">
        <Link href="/reports" className="flex items-center gap-1 text-sm" style={muted}><ArrowLeft size={14} /> Reports</Link>
        <div className="flex items-center gap-2">
          {([30, 90] as const).map((d) => (
            <button key={d} onClick={() => setDays(d)} className="px-3 py-1.5 rounded-lg text-sm"
              style={days === d ? { background: "var(--accent)", color: "#fff" } : { ...panel, color: "var(--text-primary)" }}>
              {d === 30 ? "Last 30 days" : "Last 90 days"}
            </button>
          ))}
          <button onClick={() => window.print()} disabled={!p} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm disabled:opacity-50"
            style={{ ...panel, color: "var(--text-primary)" }}>
            <Download size={14} /> Download PDF
          </button>
        </div>
      </div>
      <div className="flex flex-wrap gap-4 text-sm print:hidden" style={{ color: "var(--text-primary)" }}>
        <span style={muted}>Include:</span>
        {PARTS.filter((x) => x.key !== "data_protection" || p?.data_protection).map((x) => (
          <label key={x.key} className="flex items-center gap-1.5">
            <input type="checkbox" checked={parts.has(x.key)} onChange={(e) => {
              const next = new Set(parts);
              if (e.target.checked) next.add(x.key); else next.delete(x.key);
              setParts(next);
            }} />
            {x.label}
          </label>
        ))}
      </div>

      {isLoading && <p className="text-sm" style={muted}>Loading…</p>}
      {error && <p className="text-sm" style={{ color: "#ef4444" }}>{apiErrorMessage(error, "Could not load.")}</p>}

      {p && (
        <>
          <div className="rounded-xl p-6 break-inside-avoid" style={panel}>
            <p className="text-xs uppercase tracking-wide" style={muted}>Compliance pack · evidence from SAVIO</p>
            <h1 className="text-2xl font-semibold" style={{ color: "var(--text-primary)" }}>{p.organization}</h1>
            <p className="text-sm mt-1" style={muted}>
              {new Date(p.since).toLocaleDateString()} to {new Date(p.generated_at).toLocaleDateString()} ·
              {" "}{PARTS.filter((x) => parts.has(x.key) && (x.key !== "data_protection" || p.data_protection)).map((x) => x.label).join(", ")}
            </p>
          </div>
          <Pack p={p} parts={parts} />
          <p className="text-xs" style={muted}>{p.disclaimer} Generated {new Date(p.generated_at).toLocaleString()}.</p>
        </>
      )}
    </div>
  );
}
