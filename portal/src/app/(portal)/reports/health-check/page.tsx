"use client";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Download, ShieldCheck } from "lucide-react";
import { getHealthCheckReport, type HealthCheckReport } from "@/lib/api/reports";

// L1 — the Free IT Health Check. One printable page built from what the agent already
// collects; "Download PDF" is the browser's own print-to-PDF, so what the owner keeps is
// exactly what they saw. Every number is a count from their own fleet — no estimates.

const SEVERITY: Record<string, { label: string; color: string }> = {
  high: { label: "High", color: "#dc2626" },
  medium: { label: "Medium", color: "#d97706" },
  low: { label: "Low", color: "#2563eb" },
};
const STATUS_LABEL: Record<string, string> = {
  compliant: "Healthy", at_risk: "At risk", non_compliant: "Needs attention",
};

function scoreColor(score: number) {
  return score >= 80 ? "#16a34a" : score >= 60 ? "#d97706" : "#dc2626";
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-xl p-5 break-inside-avoid" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
      <h2 className="text-sm font-semibold uppercase tracking-wide mb-3" style={{ color: "var(--text-secondary)" }}>{title}</h2>
      {children}
    </section>
  );
}

function Nothing({ children }: { children: React.ReactNode }) {
  return <p className="text-sm" style={{ color: "var(--text-secondary)" }}>{children}</p>;
}

function List({ items }: { items: string[] }) {
  return (
    <ul className="text-sm space-y-1" style={{ color: "var(--text-primary)" }}>
      {items.map((i) => <li key={i}>• {i}</li>)}
    </ul>
  );
}

function Report({ r }: { r: HealthCheckReport }) {
  const high = r.findings.filter((f) => f.severity === "high").length;
  return (
    <div className="space-y-5 max-w-4xl mx-auto print:max-w-none">
      {/* Cover */}
      <div className="rounded-xl p-6 flex items-center gap-6 break-inside-avoid"
        style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
        <div className="flex flex-col items-center justify-center w-28 h-28 rounded-full shrink-0"
          style={{ border: `6px solid ${scoreColor(r.score)}` }}>
          <span className="text-3xl font-bold" style={{ color: scoreColor(r.score) }}>{r.score}</span>
          <span className="text-xs" style={{ color: "var(--text-secondary)" }}>out of 100</span>
        </div>
        <div className="min-w-0">
          <p className="text-xs uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>IT Health Check</p>
          <h1 className="text-2xl font-semibold" style={{ color: "var(--text-primary)" }}>{r.organization}</h1>
          <p className="text-sm mt-1" style={{ color: "var(--text-secondary)" }}>
            {r.devices} {r.devices === 1 ? "computer" : "computers"} checked · generated {r.generated_at} ·
            data from {r.days_of_data} of 7 days{r.complete ? "" : " (the full week is not in yet)"}
          </p>
          <p className="text-sm mt-2" style={{ color: "var(--text-primary)" }}>
            {r.compliant} healthy · {r.at_risk} at risk · {r.non_compliant} need attention
            {r.findings.length > 0 && <> — {r.findings.length} {r.findings.length === 1 ? "problem" : "problems"} found, {high} high-severity</>}
          </p>
        </div>
      </div>

      <Section title="What we found">
        {r.findings.length === 0 ? <Nothing>No failing security or health checks. Nothing to fix.</Nothing> : (
          <div className="space-y-4">
            {r.findings.map((f) => (
              <div key={f.key} className="break-inside-avoid">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-semibold px-2 py-0.5 rounded"
                    style={{ color: SEVERITY[f.severity]?.color, border: `1px solid ${SEVERITY[f.severity]?.color}` }}>
                    {SEVERITY[f.severity]?.label ?? f.severity}
                  </span>
                  <span className="font-medium" style={{ color: "var(--text-primary)" }}>{f.title}</span>
                  <span className="text-sm" style={{ color: "var(--text-secondary)" }}>— {f.count} {f.count === 1 ? "computer" : "computers"}</span>
                </div>
                <ul className="text-sm mt-1 ml-1" style={{ color: "var(--text-secondary)" }}>
                  {f.devices.map((d) => <li key={d}>• {d}</li>)}
                  {f.count > f.devices.length && <li>• …and {f.count - f.devices.length} more</li>}
                </ul>
                <p className="text-sm mt-1" style={{ color: "var(--text-primary)" }}><strong>What to do:</strong> {f.advice}</p>
              </div>
            ))}
          </div>
        )}
      </Section>

      <div className="grid gap-5 md:grid-cols-2 print:grid-cols-2">
        <Section title="Disks filling up within a week">
          {r.disks_filling_soon.length ? <List items={r.disks_filling_soon} /> : <Nothing>None — no disk is on course to fill this week.</Nothing>}
        </Section>
        <Section title={`Computers older than 4 years`}>
          {r.old_hardware.length ? <List items={r.old_hardware} /> : <Nothing>None found (from purchase or BIOS dates).</Nothing>}
        </Section>
        <Section title="Warranty ending in 90 days">
          {r.warranty.length ? (
            <List items={r.warranty.map((w) => `${w.asset} — ${w.expired ? "ended" : "ends"} ${w.ends}`)} />
          ) : <Nothing>None in the asset register.</Nothing>}
        </Section>
        <Section title="Software">
          <p className="text-sm" style={{ color: "var(--text-primary)" }}>
            {r.software.distinct_apps} different programs installed; {r.software.per_user_installs} installed
            by users into their own profile, outside IT&apos;s view.
          </p>
          <p className="text-sm mt-2" style={{ color: "var(--text-primary)" }}>
            {r.software.ai_tools.length
              ? <>AI tools on staff computers: {r.software.ai_tools.map((a) => `${a.name} (${a.devices})`).join(", ")}.</>
              : "No desktop AI tools found."}
          </p>
        </Section>
      </div>

      <Section title="Every computer">
        {r.per_device.length === 0 ? <Nothing>No computers have reported yet.</Nothing> : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs uppercase tracking-wide" style={{ color: "var(--text-secondary)", borderBottom: "1px solid var(--border)" }}>
                <th className="py-2 pr-3">Computer</th><th className="py-2 pr-3">Score</th>
                <th className="py-2 pr-3">Status</th><th className="py-2">Failing checks</th>
              </tr>
            </thead>
            <tbody>
              {r.per_device.map((d) => (
                <tr key={d.hostname} className="break-inside-avoid" style={{ borderBottom: "1px solid var(--border)", color: "var(--text-primary)" }}>
                  <td className="py-2 pr-3 font-medium">{d.hostname}</td>
                  <td className="py-2 pr-3" style={{ color: scoreColor(d.score) }}>{d.score}</td>
                  <td className="py-2 pr-3">{STATUS_LABEL[d.status] ?? d.status}</td>
                  <td className="py-2" style={{ color: "var(--text-secondary)" }}>{d.failed.join(", ") || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Section>

      <p className="text-xs text-center pb-2" style={{ color: "var(--text-secondary)" }}>
        Prepared by SAVIO from data collected on your computers. Counts only — nothing here is an estimate.
      </p>
    </div>
  );
}

export default function HealthCheckPage() {
  const { data, isLoading, error } = useQuery({ queryKey: ["health-check-report"], queryFn: getHealthCheckReport });

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-3 print:hidden">
        <div className="flex items-center gap-2">
          <Link href="/reports" className="p-2 rounded-lg" style={{ color: "var(--text-secondary)" }} aria-label="Back to reports">
            <ArrowLeft size={16} />
          </Link>
          <div className="p-2 rounded-lg" style={{ background: "rgba(37,99,235,0.1)", color: "var(--accent)" }}>
            <ShieldCheck size={18} />
          </div>
          <div>
            <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>IT Health Check</h1>
            <p className="text-sm mt-0.5" style={{ color: "var(--text-secondary)" }}>
              A one-page report of what SAVIO found on your computers — share it as a PDF
            </p>
          </div>
        </div>
        <button onClick={() => window.print()} disabled={!data}
          className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50"
          style={{ background: "var(--accent)" }}>
          <Download size={15} /> Download PDF
        </button>
      </div>

      {isLoading && <p className="text-sm" style={{ color: "var(--text-secondary)" }}>Building the report…</p>}
      {error && <p className="text-sm" style={{ color: "#dc2626" }}>Couldn&apos;t build the report. Only admins and technicians can open it.</p>}
      {data && <Report r={data} />}
    </div>
  );
}
