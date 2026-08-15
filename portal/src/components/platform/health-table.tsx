"use client";
/**
 * Customer health, worst first.
 *
 * The subscription status says who is paying. This table says who is likely to stop, which
 * is a different and earlier question — and it shows the reasoning next to the score,
 * because an operator will not act on a number they cannot argue with.
 */
import { useMemo, useState } from "react";
import Link from "next/link";
import { ArrowUpDown, Building2, ChevronRight } from "lucide-react";
import type { HealthBand, OrgHealthRow } from "@/lib/api/types";
import { formatMinor, formatRelativeTime } from "@/lib/utils";
import { EmptyNote, HealthPill, Meter, StatusPill } from "./console-ui";

type SortKey = "health" | "mrr" | "devices" | "quiet" | "name";
type BandFilter = HealthBand | "all";

const FILTERS: { key: BandFilter; label: string }[] = [
  { key: "all", label: "All" },
  { key: "at_risk", label: "At risk" },
  { key: "watch", label: "Watch" },
  { key: "healthy", label: "Healthy" },
];

const SORTS: { key: SortKey; label: string; align: "left" | "right" }[] = [
  { key: "name", label: "Customer", align: "left" },
  { key: "health", label: "Health", align: "left" },
  { key: "devices", label: "Fleet online", align: "left" },
  { key: "quiet", label: "Last activity", align: "left" },
  { key: "mrr", label: "MRR", align: "right" },
];

function compare(a: OrgHealthRow, b: OrgHealthRow, key: SortKey): number {
  switch (key) {
    case "name": return a.org_name.localeCompare(b.org_name);
    case "mrr": return (b.mrr_cents ?? 0) - (a.mrr_cents ?? 0);
    case "devices": return b.devices - a.devices;
    // Never-active accounts sort as the quietest — they are the extreme of the thing
    // this column measures, not missing data.
    case "quiet": return (b.days_quiet ?? Number.MAX_SAFE_INTEGER) - (a.days_quiet ?? Number.MAX_SAFE_INTEGER);
    case "health":
    default: return a.health_score - b.health_score;
  }
}

export function HealthTable({ rows, currency }: { rows: OrgHealthRow[]; currency: string | null }) {
  const [band, setBand] = useState<BandFilter>("all");
  const [sort, setSort] = useState<SortKey>("health");

  const counts = useMemo(() => {
    const c: Record<BandFilter, number> = { all: rows.length, healthy: 0, watch: 0, at_risk: 0 };
    for (const r of rows) c[r.health_band] += 1;
    return c;
  }, [rows]);

  const visible = useMemo(() => {
    const filtered = band === "all" ? rows : rows.filter((r) => r.health_band === band);
    return [...filtered].sort((a, b) => compare(a, b, sort));
  }, [rows, band, sort]);

  return (
    <div className="rounded-xl overflow-hidden" style={{ border: "1px solid var(--border)" }}>
      {/* Filters in one row above the table. */}
      <div
        className="px-4 py-3 flex items-center justify-between gap-3 flex-wrap"
        style={{ background: "var(--surface)", borderBottom: "1px solid var(--border)" }}
      >
        <div className="flex items-center gap-1.5 flex-wrap">
          {FILTERS.map((f) => {
            const active = band === f.key;
            return (
              <button
                key={f.key}
                onClick={() => setBand(f.key)}
                className="px-2.5 py-1 rounded-lg text-xs font-medium transition-colors"
                style={{
                  background: active ? "color-mix(in srgb, var(--accent) 12%, transparent)" : "transparent",
                  color: active ? "var(--accent)" : "var(--text-secondary)",
                  border: `1px solid ${active ? "var(--accent)" : "var(--border)"}`,
                }}
              >
                {f.label}
                <span className="ml-1.5 tabular-nums opacity-70">{counts[f.key]}</span>
              </button>
            );
          })}
        </div>
        <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
          {visible.length} shown
        </p>
      </div>

      <div className="overflow-x-auto" style={{ background: "var(--surface)" }}>
        <table className="w-full text-sm">
          <thead>
            <tr style={{ borderBottom: "1px solid var(--border)" }}>
              {SORTS.map((c) => (
                <th
                  key={c.key}
                  className={`px-4 py-2.5 text-${c.align} text-[11px] font-medium uppercase tracking-wide whitespace-nowrap`}
                  style={{ color: "var(--text-secondary)" }}
                >
                  <button
                    onClick={() => setSort(c.key)}
                    className="inline-flex items-center gap-1 hover:underline"
                    style={{ color: sort === c.key ? "var(--accent)" : "inherit" }}
                  >
                    {c.label}
                    <ArrowUpDown size={11} />
                  </button>
                </th>
              ))}
              <th className="px-4 py-2.5 w-8" />
            </tr>
          </thead>
          <tbody>
            {visible.map((r) => (
              <tr
                key={r.org_id}
                className="transition-colors hover:bg-brand-500/5"
                style={{ borderBottom: "1px solid var(--border)" }}
              >
                <td className="px-4 py-3 align-top">
                  <Link
                    href={`/platform/${r.org_id}`}
                    className="font-medium hover:underline"
                    style={{ color: "var(--text-primary)" }}
                  >
                    {r.org_name}
                  </Link>
                  <div className="flex items-center gap-1.5 mt-1">
                    <StatusPill status={r.subscription_status} />
                    <span className="text-xs capitalize" style={{ color: "var(--text-secondary)" }}>
                      {r.plan_tier}
                    </span>
                  </div>
                </td>

                <td className="px-4 py-3 align-top">
                  <HealthPill band={r.health_band} score={r.health_score} />
                  {/* The reasoning, not just the verdict. The rest are kept on the title so
                      one long list cannot push the table sideways. */}
                  {r.risk_reasons.length > 0 && (
                    <p
                      className="text-xs mt-1 max-w-[220px] truncate"
                      style={{ color: "var(--text-secondary)" }}
                      title={r.risk_reasons.join(" · ")}
                    >
                      {r.risk_reasons[0]}
                      {r.risk_reasons.length > 1 && (
                        <span className="opacity-70"> +{r.risk_reasons.length - 1}</span>
                      )}
                    </p>
                  )}
                </td>

                <td className="px-4 py-3 align-top whitespace-nowrap">
                  {r.devices === 0 ? (
                    <span className="text-xs" style={{ color: "var(--health-bad)" }}>
                      None enrolled
                    </span>
                  ) : (
                    <span className="flex items-center gap-2">
                      <Meter
                        value={r.online_devices}
                        max={r.devices}
                        color={
                          (r.online_pct ?? 0) >= 75 ? "var(--health-good)"
                            : (r.online_pct ?? 0) >= 40 ? "var(--health-warn)"
                              : "var(--health-bad)"
                        }
                      />
                      <span className="tabular-nums text-xs" style={{ color: "var(--text-secondary)" }}>
                        {r.online_devices}/{r.devices}
                      </span>
                    </span>
                  )}
                  {r.licenses > 0 && (
                    <p className="text-xs mt-1 tabular-nums" style={{ color: "var(--text-secondary)" }}>
                      {r.devices} of {r.licenses} seats deployed
                    </p>
                  )}
                </td>

                <td className="px-4 py-3 align-top whitespace-nowrap">
                  {r.last_activity_at ? (
                    <>
                      <span
                        className="text-xs"
                        style={{
                          color: (r.days_quiet ?? 0) >= 7 ? "var(--health-warn)" : "var(--text-secondary)",
                        }}
                      >
                        {formatRelativeTime(r.last_activity_at)}
                      </span>
                      <p className="text-xs mt-1 tabular-nums" style={{ color: "var(--text-secondary)" }}>
                        {r.users} user{r.users === 1 ? "" : "s"}
                      </p>
                    </>
                  ) : (
                    <span className="text-xs" style={{ color: "var(--health-bad)" }}>Never</span>
                  )}
                </td>

                <td className="px-4 py-3 align-top text-right tabular-nums whitespace-nowrap"
                  style={{ color: "var(--text-primary)" }}>
                  {formatMinor(r.mrr_cents, currency)}
                  {r.trial_days_left != null && (
                    <p className="text-xs mt-1" style={{ color: "var(--health-warn)" }}>
                      Trial · {r.trial_days_left}d left
                    </p>
                  )}
                </td>

                <td className="px-4 py-3 align-top">
                  <Link href={`/platform/${r.org_id}`} aria-label={`Open ${r.org_name}`}>
                    <ChevronRight size={15} style={{ color: "var(--text-secondary)" }} />
                  </Link>
                </td>
              </tr>
            ))}
            {visible.length === 0 && (
              <tr>
                <td colSpan={6}>
                  <EmptyNote
                    icon={Building2}
                    text={
                      rows.length === 0
                        ? "No customer organizations yet."
                        : "No customers in this band."
                    }
                  />
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
