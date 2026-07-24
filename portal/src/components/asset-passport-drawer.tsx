"use client";
import React from "react";
import { useQuery } from "@tanstack/react-query";
import {
  X, History, UserPlus, UserMinus, Wrench, MapPin, PackagePlus,
  MailCheck, ScrollText, Archive, RotateCcw,
} from "lucide-react";
import { getAssetPassport } from "@/lib/api/assets";
import type { Asset, AssetEvent } from "@/lib/api/types";

const STATUS_LABEL: Record<string, string> = {
  in_use: "In use", in_storage: "Idle / storage", in_repair: "In repair",
  retired: "Retired", lost: "Lost",
};
const STATUS_COLOR: Record<string, string> = {
  in_use: "#10b981", in_storage: "#b246d4", in_repair: "#f59e0b", retired: "#64748b", lost: "#ef4444",
};

function fmtDuration(seconds: number): string {
  const d = Math.floor(seconds / 86400);
  if (d >= 1) return `${d}d`;
  const h = Math.floor(seconds / 3600);
  if (h >= 1) return `${h}h`;
  return `${Math.max(1, Math.floor(seconds / 60))}m`;
}
function sinceText(iso: string): string {
  const days = Math.floor((Date.now() - new Date(iso).getTime()) / 86_400_000);
  return days <= 0 ? "today" : `${days}d ago`;
}
function eventIcon(t: AssetEvent["event_type"]) {
  switch (t) {
    case "created": return PackagePlus;
    case "assigned": return UserPlus;
    case "unassigned": return UserMinus;
    case "status_changed": return Wrench;
    case "location_changed": return MapPin;
    case "acknowledged": return MailCheck;
    case "archived": return Archive;
    case "restored": return RotateCcw;
    default: return ScrollText;
  }
}
function eventTitle(e: AssetEvent): React.ReactNode {
  const label = (v: string | null) => (v ? STATUS_LABEL[v] ?? v : "—");
  switch (e.event_type) {
    case "created": return <>Registered <span style={{ color: "var(--text-secondary)" }}>({label(e.to_value)})</span></>;
    case "assigned": return e.from_value
      ? <>Reassigned to <strong>{e.to_value ?? e.user_name}</strong> <span style={{ color: "var(--text-secondary)" }}>(from {e.from_value})</span></>
      : <>Assigned to <strong>{e.to_value ?? e.user_name}</strong></>;
    case "unassigned": return <>Unassigned <span style={{ color: "var(--text-secondary)" }}>(from {e.from_value ?? "—"})</span></>;
    case "status_changed": return <>Status <span>{label(e.from_value)}</span> → <strong>{label(e.to_value)}</strong></>;
    case "location_changed": return <>Location <span>{e.from_value ?? "—"}</span> → <strong>{e.to_value ?? "—"}</strong></>;
    case "acknowledged": return <>Receipt acknowledged by <strong>{e.user_name ?? e.to_value}</strong></>;
    case "archived": return <>Archived <span style={{ color: "var(--text-secondary)" }}>(retired from the active register)</span></>;
    case "restored": return <>Restored to the active register</>;
    default: return e.note ?? "Note";
  }
}

export function AssetPassportDrawer({ asset, onClose }: { asset: Asset; onClose: () => void }) {
  const { data: p, isLoading } = useQuery({
    queryKey: ["asset-passport", asset.id],
    queryFn: () => getAssetPassport(asset.id),
  });
  const totalSecs = (p?.time_in_status ?? []).reduce((s, d) => s + d.seconds, 0) || 1;
  const cell = { background: "var(--bg)", border: "1px solid var(--border)" } as const;

  return (
    <div className="fixed inset-0 z-50 flex justify-end" style={{ background: "rgba(0,0,0,0.4)" }} onClick={onClose}>
      <div onClick={(e) => e.stopPropagation()} className="w-full max-w-lg h-full overflow-y-auto p-6 space-y-5"
        style={{ background: "var(--surface)", borderLeft: "1px solid var(--border)" }}>
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-2">
            <div className="p-2 rounded-lg" style={{ background: "rgba(154,47,187,0.1)", color: "var(--accent)" }}><History size={18} /></div>
            <div>
              <h2 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>Device passport</h2>
              <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
                {asset.name}{asset.serial_number ? ` · SN ${asset.serial_number}` : ""}
              </p>
            </div>
          </div>
          <button onClick={onClose} style={{ color: "var(--text-secondary)" }}><X size={18} /></button>
        </div>

        {isLoading && <p className="text-sm" style={{ color: "var(--text-secondary)" }}>Loading history…</p>}

        {p && (
          <>
            <div className="grid grid-cols-2 gap-2.5">
              <div className="rounded-lg p-3" style={cell}>
                <p className="text-[11px] uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>Current status</p>
                <span className="mt-1 inline-block text-xs font-medium px-2 py-0.5 rounded-full"
                  style={{ color: STATUS_COLOR[p.current_status], background: `${STATUS_COLOR[p.current_status]}1a` }}>
                  {STATUS_LABEL[p.current_status] ?? p.current_status}
                </span>
              </div>
              <div className="rounded-lg p-3" style={cell}>
                <p className="text-[11px] uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>Holder</p>
                <p className="text-sm font-medium mt-1" style={{ color: "var(--text-primary)" }}>{p.current_holder ?? "Unassigned"}</p>
                {p.holder_since && <p className="text-[11px]" style={{ color: "var(--text-secondary)" }}>since {sinceText(p.holder_since)}</p>}
              </div>
              <div className="rounded-lg p-3" style={cell}>
                <p className="text-[11px] uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>Age</p>
                <p className="text-sm font-medium mt-1" style={{ color: "var(--text-primary)" }}>{p.age_days}d</p>
                <p className="text-[11px]" style={{ color: "var(--text-secondary)" }}>{p.assignment_count} assignment{p.assignment_count === 1 ? "" : "s"} · {p.repair_count} repair{p.repair_count === 1 ? "" : "s"}</p>
              </div>
              <div className="rounded-lg p-3" style={cell}>
                <p className="text-[11px] uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>Location</p>
                <p className="text-sm font-medium mt-1" style={{ color: "var(--text-primary)" }}>{p.current_location ?? "—"}</p>
              </div>
            </div>

            {p.time_in_status.length > 0 && (
              <div>
                <p className="text-xs font-medium uppercase tracking-wide mb-2" style={{ color: "var(--text-secondary)" }}>Time in status</p>
                <div className="flex h-2.5 rounded-full overflow-hidden mb-2" style={{ background: "var(--bg)" }}>
                  {p.time_in_status.map((d) => (
                    <span key={d.status} style={{ width: `${(d.seconds / totalSecs) * 100}%`, background: STATUS_COLOR[d.status] ?? "#64748b" }}
                      title={`${STATUS_LABEL[d.status] ?? d.status}: ${fmtDuration(d.seconds)}`} />
                  ))}
                </div>
                <div className="flex flex-wrap gap-x-4 gap-y-1">
                  {p.time_in_status.map((d) => (
                    <span key={d.status} className="inline-flex items-center gap-1.5 text-xs" style={{ color: "var(--text-secondary)" }}>
                      <span className="inline-block w-2.5 h-2.5 rounded-sm" style={{ background: STATUS_COLOR[d.status] ?? "#64748b" }} />
                      {STATUS_LABEL[d.status] ?? d.status}: <span style={{ color: "var(--text-primary)" }}>{fmtDuration(d.seconds)}</span>
                    </span>
                  ))}
                </div>
              </div>
            )}

            <div>
              <p className="text-xs font-medium uppercase tracking-wide mb-3" style={{ color: "var(--text-secondary)" }}>History</p>
              <div className="space-y-0">
                {p.events.map((e, i) => {
                  const Icon = eventIcon(e.event_type);
                  return (
                    <div key={e.id} className="flex gap-3">
                      <div className="flex flex-col items-center">
                        <div className="p-1.5 rounded-full shrink-0" style={{ background: "rgba(154,47,187,0.1)", color: "var(--accent)" }}><Icon size={13} /></div>
                        {i < p.events.length - 1 && <div className="w-px flex-1 my-1" style={{ background: "var(--border)" }} />}
                      </div>
                      <div className="pb-4 min-w-0">
                        <p className="text-sm" style={{ color: "var(--text-primary)" }}>{eventTitle(e)}</p>
                        <p className="text-[11px] mt-0.5" style={{ color: "var(--text-secondary)" }}>
                          {new Date(e.occurred_at).toLocaleString()}{e.actor_name ? ` · by ${e.actor_name}` : ""}
                        </p>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
