"use client";
import { useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { PackagePlus, ChevronDown, ChevronRight } from "lucide-react";
import { getMe } from "@/lib/api/auth";
import { listDevicesPaged } from "@/lib/api/devices";
import { listDeviceGroups } from "@/lib/api/grouping";
import { getSoftwareCatalog, pushInstall, listDeployments, getDeployment } from "@/lib/api/software";
import { apiErrorMessage } from "@/lib/utils";

const STATUS_COLOR: Record<string, string> = {
  succeeded: "#10b981", failed: "#ef4444", dispatched: "#2563eb", approved: "#64748b",
  pending_approval: "#d97706", rejected: "#64748b",
};
const STATUS_LABEL: Record<string, string> = {
  approved: "Waiting for device", dispatched: "Installing", succeeded: "Installed",
  failed: "Failed", pending_approval: "Needs approval", rejected: "Rejected",
};

const card = { background: "var(--surface)", border: "1px solid var(--border)" };
const input = { background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" };

export default function SoftwarePage() {
  const qc = useQueryClient();
  const { data: me } = useQuery({ queryKey: ["me"], queryFn: getMe });
  const isStaff = me?.role === "admin" || me?.role === "technician";
  const { data: catalog } = useQuery({ queryKey: ["software-catalog"], queryFn: getSoftwareCatalog, enabled: isStaff });
  const { data: devicePage } = useQuery({ queryKey: ["software-devices"], queryFn: () => listDevicesPaged({ page_size: 500 }), enabled: isStaff });
  const { data: groups } = useQuery({ queryKey: ["device-groups"], queryFn: listDeviceGroups, enabled: isStaff });
  const { data: deployments } = useQuery({ queryKey: ["deployments"], queryFn: listDeployments, enabled: isStaff, refetchInterval: 15_000 });

  const [pkg, setPkg] = useState("");
  const [deviceIds, setDeviceIds] = useState<Set<string>>(new Set());
  const [groupIds, setGroupIds] = useState<Set<string>>(new Set());
  const [excluded, setExcluded] = useState<Set<string>>(new Set());
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [open, setOpen] = useState<string | null>(null);

  const devices = devicePage?.items ?? [];
  const byCategory = useMemo(() => {
    const m = new Map<string, typeof catalog>();
    for (const c of catalog ?? []) m.set(c.category, [...(m.get(c.category) ?? []), c]);
    return [...m.entries()];
  }, [catalog]);

  const toggle = (set: Set<string>, setter: (s: Set<string>) => void, id: string) => {
    const next = new Set(set); if (next.has(id)) next.delete(id); else next.add(id); setter(next);
  };

  async function push() {
    if (!pkg) { setMsg({ ok: false, text: "Choose the software to install." }); return; }
    if (!deviceIds.size && !groupIds.size) { setMsg({ ok: false, text: "Choose at least one device or group." }); return; }
    if (reason.trim().length < 3) { setMsg({ ok: false, text: "Say why — it goes in the audit log." }); return; }
    const name = catalog?.find((c) => c.package_id === pkg)?.name ?? pkg;
    if (!confirm(`Install ${name} on the selected devices${groupIds.size ? " and groups" : ""}?`)) return;
    setBusy(true); setMsg(null);
    try {
      const r = await pushInstall({ package_id: pkg, device_ids: [...deviceIds], group_ids: [...groupIds],
                                    exclude_device_ids: [...excluded], reason: reason.trim() });
      const parts = [`${r.queued} queued`];
      if (r.already_running) parts.push(`${r.already_running} already in progress`);
      if (r.failed) parts.push(`${r.failed} failed`);
      if (r.not_attempted) parts.push(`${r.not_attempted} not attempted`);
      setMsg({ ok: !r.failed, text: `${r.title}: ${parts.join(", ")}.${r.error ? " " + r.error : ""} Offline PCs install when they next come online.` });
      setDeviceIds(new Set()); setGroupIds(new Set()); setExcluded(new Set()); setReason("");
      qc.invalidateQueries({ queryKey: ["deployments"] });
      setOpen(r.id);
    } catch (err) {
      setMsg({ ok: false, text: apiErrorMessage(err, "Couldn't start the push.") });
    } finally { setBusy(false); }
  }

  if (me && !isStaff) {
    return <p className="text-sm" style={{ color: "var(--text-secondary)" }}>Software pushes are for IT staff (technicians and admins).</p>;
  }

  return (
    <div className="space-y-4 max-w-5xl">
      <div className="flex items-start gap-3">
        <div className="p-2 rounded-lg" style={{ background: "rgba(37,99,235,0.12)", color: "#2563eb" }}><PackagePlus size={18} /></div>
        <div>
          <h1 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>Software</h1>
          <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
            Install software from SAVIO&apos;s catalog on chosen PCs or groups — silently, for every user of the PC. Each install is audited.
          </p>
        </div>
      </div>

      <div className="rounded-xl p-4 space-y-4" style={card}>
        <div>
          <label className="block text-xs font-medium mb-1" style={{ color: "var(--text-secondary)" }}>1 · Software</label>
          <select value={pkg} onChange={(e) => setPkg(e.target.value)} className="w-full px-3 py-2 rounded-lg text-sm outline-none" style={input}>
            <option value="">Choose…</option>
            {byCategory.map(([cat, items]) => (
              <optgroup key={cat} label={cat}>
                {(items ?? []).map((c) => <option key={c.package_id} value={c.package_id}>{c.name} — {c.publisher}</option>)}
              </optgroup>
            ))}
          </select>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-medium mb-1" style={{ color: "var(--text-secondary)" }}>2 · Groups</label>
            <div className="rounded-lg p-2 max-h-48 overflow-y-auto space-y-1" style={input}>
              {(groups ?? []).map((g) => (
                <label key={g.id} className="flex items-center gap-2 text-sm">
                  <input type="checkbox" checked={groupIds.has(g.id)} onChange={() => toggle(groupIds, setGroupIds, g.id)} />
                  {g.name} <span className="text-xs" style={{ color: "var(--text-secondary)" }}>({g.device_count})</span>
                </label>
              ))}
              {!groups?.length && <p className="text-xs" style={{ color: "var(--text-secondary)" }}>No groups yet.</p>}
            </div>
          </div>
          <div>
            <label className="block text-xs font-medium mb-1" style={{ color: "var(--text-secondary)" }}>
              …and/or devices · tick <b>Skip</b> to leave a device out
            </label>
            <div className="rounded-lg p-2 max-h-48 overflow-y-auto space-y-1" style={input}>
              {devices.map((d) => (
                <div key={d.id} className="flex items-center justify-between gap-2 text-sm">
                  <label className="flex items-center gap-2">
                    <input type="checkbox" checked={deviceIds.has(d.id)} onChange={() => toggle(deviceIds, setDeviceIds, d.id)} />
                    {d.hostname} <span className="text-xs" style={{ color: d.status === "online" ? "#10b981" : "var(--text-secondary)" }}>{d.status}</span>
                  </label>
                  <label className="flex items-center gap-1 text-xs" style={{ color: "var(--text-secondary)" }}>
                    <input type="checkbox" checked={excluded.has(d.id)} onChange={() => toggle(excluded, setExcluded, d.id)} /> Skip
                  </label>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div>
          <label className="block text-xs font-medium mb-1" style={{ color: "var(--text-secondary)" }}>3 · Reason (for the audit log)</label>
          <input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. Standard browser for Finance" maxLength={500}
            className="w-full px-3 py-2 rounded-lg text-sm outline-none" style={input} />
        </div>

        {msg && <p className="text-xs" style={{ color: msg.ok ? "#10b981" : "#ef4444" }}>{msg.text}</p>}
        <div className="flex justify-end">
          <button onClick={push} disabled={busy} className="px-4 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50" style={{ background: "#2563eb" }}>
            {busy ? "Starting…" : "Install"}
          </button>
        </div>
      </div>

      <div className="rounded-xl p-4" style={card}>
        <h2 className="text-sm font-semibold mb-2" style={{ color: "var(--text-primary)" }}>Recent pushes</h2>
        {(deployments ?? []).map((d) => (
          <div key={d.id} style={{ borderTop: "1px solid var(--border)" }}>
            <button onClick={() => setOpen(open === d.id ? null : d.id)} className="w-full flex items-center justify-between gap-3 py-2 text-left">
              <span className="flex items-center gap-1.5 text-sm" style={{ color: "var(--text-primary)" }}>
                {open === d.id ? <ChevronDown size={14} /> : <ChevronRight size={14} />} {d.title}
                <span className="text-xs" style={{ color: "var(--text-secondary)" }}>· {new Date(d.created_at).toLocaleString()} · {d.reason}</span>
              </span>
              <span className="text-xs whitespace-nowrap">
                {Object.entries(d.status_counts).map(([s, n]) => (
                  <span key={s} className="ml-2" style={{ color: STATUS_COLOR[s] ?? "var(--text-secondary)" }}>{n} {STATUS_LABEL[s] ?? s}</span>
                ))}
              </span>
            </button>
            {open === d.id && <DeploymentRows id={d.id} />}
          </div>
        ))}
        {!deployments?.length && <p className="text-xs" style={{ color: "var(--text-secondary)" }}>Nothing pushed yet.</p>}
      </div>
    </div>
  );
}

function DeploymentRows({ id }: { id: string }) {
  const { data } = useQuery({ queryKey: ["deployment", id], queryFn: () => getDeployment(id), refetchInterval: 10_000 });
  return (
    <table className="w-full text-sm mb-2"><tbody>
      {(data?.devices ?? []).map((r) => (
        <tr key={r.device_id} style={{ borderTop: "1px solid var(--border)" }}>
          <td className="py-1.5 pl-6" style={{ color: "var(--text-primary)" }}>{r.hostname}</td>
          <td className="py-1.5" style={{ color: STATUS_COLOR[r.status] ?? "var(--text-secondary)" }}>{STATUS_LABEL[r.status] ?? r.status}</td>
          <td className="py-1.5 text-xs" style={{ color: "var(--text-secondary)" }}>{r.message ?? ""}</td>
        </tr>
      ))}
    </tbody></table>
  );
}
