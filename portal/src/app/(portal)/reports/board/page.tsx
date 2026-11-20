"use client";
import { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Download } from "lucide-react";
import { getBoardReport } from "@/lib/api/reports";
import { isUpgradeRequired, UpgradeRequired, requiredFeature } from "@/components/upgrade-required";
import { apiErrorMessage } from "@/lib/utils";

// Phase 3b · J3 — the board report. A month or a quarter on one page for the owner or the board,
// printed with the browser's own print-to-PDF (as L1). Counts only: no person is named, so staff
// can print it. Every number is from SAVIO's own records.

const SEVERITY: Record<string, string> = { high: "#dc2626", medium: "#d97706", low: "#2563eb" };
const color = (n: number) => (n >= 80 ? "#16a34a" : n >= 60 ? "#d97706" : "#dc2626");

function Tile({ label, value, sub, tone }: { label: string; value: string; sub?: string; tone?: string }) {
  return (
    <div className="rounded-xl p-4 break-inside-avoid" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
      <div className="text-xs uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>{label}</div>
      <div className="text-2xl font-bold mt-1" style={{ color: tone ?? "var(--text-primary)" }}>{value}</div>
      {sub && <div className="text-xs mt-0.5" style={{ color: "var(--text-secondary)" }}>{sub}</div>}
    </div>
  );
}

export default function BoardReportPage() {
  const [days, setDays] = useState<30 | 90>(30);
  const { data: r, error, isLoading } = useQuery({ queryKey: ["board-report", days], queryFn: () => getBoardReport(days), retry: false });
  const muted = { color: "var(--text-secondary)" };
  const panel = { background: "var(--surface)", border: "1px solid var(--border)" };

  if (isUpgradeRequired(error)) return <UpgradeRequired feature={requiredFeature(error)} />;

  return (
    <div className="space-y-5 max-w-4xl mx-auto print:max-w-none">
      <div className="flex items-center justify-between gap-3 print:hidden">
        <Link href="/reports" className="flex items-center gap-1 text-sm" style={muted}><ArrowLeft size={14} /> Reports</Link>
        <div className="flex items-center gap-2">
          {([30, 90] as const).map((d) => (
            <button key={d} onClick={() => setDays(d)} className="px-3 py-1.5 rounded-lg text-sm"
              style={days === d ? { background: "var(--accent)", color: "#fff" } : { ...panel, color: "var(--text-primary)" }}>
              {d === 30 ? "Last month" : "Last quarter"}
            </button>
          ))}
          <button onClick={() => window.print()} disabled={!r} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm disabled:opacity-50"
            style={{ ...panel, color: "var(--text-primary)" }}>
            <Download size={14} /> Download PDF
          </button>
        </div>
      </div>

      {isLoading && <p className="text-sm" style={muted}>Loading…</p>}
      {error && <p className="text-sm" style={{ color: "#ef4444" }}>{apiErrorMessage(error, "Could not load.")}</p>}

      {r && (
        <>
          <div className="rounded-xl p-6 break-inside-avoid" style={panel}>
            <p className="text-xs uppercase tracking-wide" style={muted}>{r.title}</p>
            <h1 className="text-2xl font-semibold" style={{ color: "var(--text-primary)" }}>{r.organization}</h1>
            <p className="text-sm mt-1" style={muted}>
              {new Date(r.since).toLocaleDateString()} to {new Date(r.generated_at).toLocaleDateString()}
            </p>
            <p className="text-base mt-3" style={{ color: "var(--text-primary)" }}>{r.headline}</p>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 print:grid-cols-4">
            <Tile label="IT health" value={`${r.kpis.health_score}/100`} sub={`${r.kpis.devices} computers`} tone={color(r.kpis.health_score)} />
            <Tile label="Fixed by SAVIO" value={r.kpis.fixed_unattended.toLocaleString()}
              sub={`about ${r.kpis.hours_saved} hours of IT work`} />
            <Tile label="Saved" value={r.kpis.inr_saved != null ? `₹${r.kpis.inr_saved.toLocaleString()}` : "—"}
              sub={r.kpis.inr_saved != null ? "at your hourly IT cost" : "set an hourly cost to see this"} />
            {r.kpis.dpdp_score != null ? (
              <Tile label="DPDP readiness" value={`${r.kpis.dpdp_score}%`} tone={color(r.kpis.dpdp_score)}
                sub={`${r.kpis.breaches_found} breach record(s) this period, ${r.kpis.breaches_open} open`} />
            ) : <Tile label="DPDP readiness" value="—" sub="with AI Guard" />}
          </div>

          {r.risks.length > 0 && (
            <section className="rounded-xl p-5 break-inside-avoid" style={panel}>
              <h2 className="text-sm font-semibold uppercase tracking-wide mb-3" style={muted}>Top risks</h2>
              <ol className="space-y-2">
                {r.risks.map((k) => (
                  <li key={k.title} className="text-sm" style={{ color: "var(--text-primary)" }}>
                    <span className="font-medium">{k.title}</span>
                    <span className="text-xs ml-2 px-1.5 py-0.5 rounded" style={{ color: SEVERITY[k.severity] ?? "inherit", border: "1px solid currentColor" }}>
                      {k.severity}</span>
                    <span style={muted}> · {k.count} computer(s)</span>
                    <div className="text-xs" style={muted}>{k.advice}</div>
                  </li>
                ))}
              </ol>
            </section>
          )}

          <div className="grid gap-4 md:grid-cols-2 print:grid-cols-2">
            {r.sections.map((s) => (
              <section key={s.key} className="rounded-xl p-5 break-inside-avoid" style={panel}>
                <h2 className="text-sm font-semibold uppercase tracking-wide mb-2" style={muted}>{s.title}</h2>
                <ul className="text-sm space-y-1" style={{ color: "var(--text-primary)" }}>
                  {s.lines.map((l) => <li key={l}>• {l}</li>)}
                </ul>
              </section>
            ))}
          </div>

          <p className="text-xs" style={muted}>{r.footer} Generated {new Date(r.generated_at).toLocaleString()}.</p>
        </>
      )}
    </div>
  );
}
