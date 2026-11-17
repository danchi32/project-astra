"use client";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { FolderSearch, ShieldAlert } from "lucide-react";
import { FINDING_KINDS, getDiscovery, type DiscoveryFolder, type FindingKind } from "@/lib/api/guard";
import { isUpgradeRequired } from "@/components/upgrade-required";
import { apiErrorMessage } from "@/lib/utils";

// Phase 3 · D5 · AI Guard → Where data lives. Each PC's weekly map of which folders hold
// sensitive files, in counts. The scan ran on the PC, in a process with no network; only
// folder paths and counts arrived here, never file names or contents. Admin only.

const status = (e: unknown) => (e as { response?: { status?: number } } | null)?.response?.status;

function kinds(counts: DiscoveryFolder["counts"], contactLists: number) {
  const parts = (Object.entries(counts) as [FindingKind, number][])
    .filter(([, n]) => n > 0).sort((a, b) => b[1] - a[1])
    .map(([k, n]) => `${FINDING_KINDS[k] ?? k} ×${n.toLocaleString()}`);
  if (contactLists) parts.push(`${contactLists} contact list${contactLists > 1 ? "s" : ""}`);
  return parts.join(", ");
}

export default function DiscoveryPage() {
  const { data, error, isLoading } = useQuery({ queryKey: ["guard-discovery"], queryFn: getDiscovery, retry: false });
  const [pc, setPc] = useState<string>("all");

  const muted = { color: "var(--text-secondary)" };
  const panel = { background: "var(--surface)", border: "1px solid var(--border)" };

  if (isUpgradeRequired(error) || status(error) === 403) {
    return (
      <div className="rounded-xl p-8 text-center max-w-lg mx-auto" style={panel}>
        <ShieldAlert size={22} className="mx-auto mb-3" style={{ color: "var(--accent)" }} />
        <h2 className="text-base font-semibold" style={{ color: "var(--text-primary)" }}>
          {isUpgradeRequired(error) ? "AI Guard is an add-on" : "Only an admin can see this"}
        </h2>
      </div>
    );
  }

  const devices = (data?.devices ?? []).filter((d) => pc === "all" || d.device_id === pc);
  const rows = devices.flatMap((d) => d.folders.map((f) => ({ ...f, hostname: d.hostname, key: `${d.device_id}|${f.path}` })))
    .sort((a, b) => b.files_with_findings - a.files_with_findings);

  return (
    <div className="space-y-4 max-w-6xl">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div className="flex items-start gap-3">
          <div className="p-2 rounded-lg" style={{ background: "rgba(37,99,235,0.12)", color: "var(--accent)" }}><FolderSearch size={18} /></div>
          <div>
            <h1 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>Where data lives</h1>
            <p className="text-xs max-w-2xl" style={muted}>
              Folders on your PCs that hold files with Aadhaar, PAN, card, bank or mobile numbers, from each PC&apos;s weekly
              check. The check runs on the PC itself; only the folder and the counts come here, never file names or contents.
              Switch it on under Browser policy.
            </p>
          </div>
        </div>
        {(data?.devices.length ?? 0) > 1 && (
          <select value={pc} onChange={(e) => setPc(e.target.value)} className="px-3 py-1.5 rounded-lg text-sm outline-none"
            style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }}>
            <option value="all">All PCs</option>
            {data!.devices.map((d) => <option key={d.device_id} value={d.device_id}>{d.hostname}</option>)}
          </select>
        )}
      </div>

      {isLoading && <p className="text-sm" style={muted}>Loading…</p>}
      {error && <p className="text-sm" style={{ color: "#ef4444" }}>{apiErrorMessage(error, "Could not load.")}</p>}

      {data && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {([["PCs checked", data.pcs], ["Files with sensitive data", data.files_with_findings],
               ["Contact lists", data.contact_lists], ["Folders", rows.length]] as const).map(([label, n]) => (
              <div key={label} className="rounded-xl p-4" style={panel}>
                <div className="text-xs" style={muted}>{label}</div>
                <div className="text-2xl font-semibold mt-1" style={{ color: "var(--text-primary)" }}>{n.toLocaleString()}</div>
              </div>
            ))}
          </div>
          {Object.keys(data.kinds).length > 0 && (
            <p className="text-xs" style={muted}>Across all PCs: {kinds(data.kinds, 0)}</p>
          )}

          <div className="rounded-xl overflow-x-auto" style={panel}>
            <table className="w-full text-sm">
              <thead>
                <tr style={{ borderBottom: "1px solid var(--border)" }}>
                  {["Folder", "PC", "Files with data", "What"].map((h) => (
                    <th key={h} className="text-left px-4 py-2 text-xs uppercase whitespace-nowrap" style={muted}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((f) => (
                  <tr key={f.key} style={{ borderBottom: "1px solid var(--border)", color: "var(--text-primary)" }}>
                    <td className="px-4 py-2 font-mono text-xs break-all">{f.path}</td>
                    <td className="px-4 py-2 text-xs whitespace-nowrap">{f.hostname}</td>
                    <td className="px-4 py-2 text-xs whitespace-nowrap">{f.files_with_findings} of {f.files}</td>
                    <td className="px-4 py-2 text-xs">{kinds(f.counts, f.contact_lists)}</td>
                  </tr>
                ))}
                {!rows.length && (
                  <tr><td colSpan={4} className="px-4 py-6 text-center text-sm" style={muted}>
                    {data.pcs ? "No sensitive files found on the PCs checked." : "No PC has reported yet. Switch the check on under Browser policy; each PC runs it within a couple of hours, then weekly."}
                  </td></tr>
                )}
              </tbody>
            </table>
          </div>

          {devices.length > 0 && (
            <p className="text-xs" style={muted}>
              {devices.map((d) => `${d.hostname}: ${d.files_scanned.toLocaleString()} files checked ${new Date(d.scanned_at).toLocaleDateString()}`
                + (d.truncated ? " (stopped at the limit)" : "")).join(" · ")}
            </p>
          )}
        </>
      )}
    </div>
  );
}
