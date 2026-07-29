"use client";
import { useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronLeft, Monitor, UserX, Trash2, DownloadCloud, Pencil, X } from "lucide-react";
import { getDevice, deleteDevice } from "@/lib/api/devices";
import { getDeviceTelemetry, getDeviceEvents, getDeviceApps, getDeviceServices, getDeviceUpdates } from "@/lib/api/device-detail";
import { listAssets, updateAsset, createAsset, getAssetPassport, resendAcknowledgement } from "@/lib/api/assets";
import { listUsers } from "@/lib/api/users";
import { listLocations } from "@/lib/api/locations";
import { getMe } from "@/lib/api/auth";
import { createRemediation, approveRemediation } from "@/lib/api/remediation";
import { DeviceStatusBadge } from "@/components/device-status-badge";
import { SearchableSelect } from "@/components/searchable-select";
import { formatRam, formatStorage, apiErrorMessage } from "@/lib/utils";
import { ASSET_STATUS_LABELS } from "@/lib/chart-colors";
import type { AssetInput, AssetCategory, AssetStatus } from "@/lib/api/types";

const CATEGORIES: AssetCategory[] = [
  "laptop", "desktop", "server", "monitor", "phone", "tablet",
  "peripheral", "network", "license", "software", "other",
];
const STATUSES: AssetStatus[] = ["in_use", "in_storage", "in_repair", "retired", "lost"];

type Tab = "overview" | "telemetry" | "events" | "software" | "services" | "updates" | "assignment" | "history";
const TABS: { key: Tab; label: string }[] = [
  { key: "overview", label: "Overview" },
  { key: "telemetry", label: "Telemetry" },
  { key: "events", label: "Event Log" },
  { key: "software", label: "Software" },
  { key: "services", label: "Services" },
  { key: "updates", label: "Windows Updates" },
  { key: "assignment", label: "Assignment" },
  { key: "history", label: "History" },
];

const LEVEL_COLOR: Record<string, string> = { Error: "#ef4444", Warning: "#f59e0b", Information: "#64748b" };

function Gauge({ label, value, sub }: { label: string; value: number; sub: string }) {
  const color = value >= 90 ? "#ef4444" : value >= 70 ? "#f59e0b" : "#10b981";
  return (
    <div className="rounded-xl p-4" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
      <p className="text-xs uppercase tracking-wide mb-2" style={{ color: "var(--text-secondary)" }}>{label}</p>
      <p className="text-2xl font-semibold" style={{ color: "var(--text-primary)" }}>{value.toFixed(0)}%</p>
      <div className="mt-2 h-1.5 rounded-full" style={{ background: "var(--bg)" }}>
        <div className="h-full rounded-full" style={{ width: `${Math.min(value, 100)}%`, background: color }} />
      </div>
      <p className="text-xs mt-1.5" style={{ color: "var(--text-secondary)" }}>{sub}</p>
    </div>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-4 py-2 border-b text-sm" style={{ borderColor: "var(--border)" }}>
      <span style={{ color: "var(--text-secondary)" }}>{label}</span>
      <span className="text-right font-medium" style={{ color: "var(--text-primary)" }}>{value ?? "—"}</span>
    </div>
  );
}

export default function DeviceDetailPage() {
  const params = useParams();
  const id = String(params.id);
  const qc = useQueryClient();
  const [tab, setTab] = useState<Tab>("overview");
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);

  const { data: me } = useQuery({ queryKey: ["me"], queryFn: getMe });
  const isAdmin = me?.role === "admin";
  const isStaff = me?.role === "admin" || me?.role === "technician";

  // Asset details editor (location, warranty, purchase date, cost, status, tag, notes…).
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState<AssetInput>({ name: "", category: "laptop", status: "in_use" });
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState("");

  const { data: device, isLoading } = useQuery({ queryKey: ["device", id], queryFn: () => getDevice(id) });
  const { data: telemetry } = useQuery({ queryKey: ["telemetry", id], queryFn: () => getDeviceTelemetry(id), refetchInterval: 30_000 });
  const { data: events } = useQuery({ queryKey: ["dev-events", id], queryFn: () => getDeviceEvents(id), enabled: tab === "events" });
  const { data: apps } = useQuery({ queryKey: ["dev-apps", id], queryFn: () => getDeviceApps(id), enabled: tab === "software" });
  const { data: services } = useQuery({ queryKey: ["dev-services", id], queryFn: () => getDeviceServices(id), enabled: tab === "services" });
  const { data: updates } = useQuery({ queryKey: ["dev-updates", id], queryFn: () => getDeviceUpdates(id), enabled: tab === "updates" });
  const { data: assets } = useQuery({ queryKey: ["assets"], queryFn: () => listAssets() });
  const { data: users } = useQuery({ queryKey: ["users"], queryFn: listUsers });
  const { data: managedLocations } = useQuery({ queryKey: ["locations"], queryFn: listLocations });

  const asset = assets?.find((a) => a.device_id === id) ?? null;
  const { data: passport } = useQuery({
    queryKey: ["asset-passport", asset?.id], queryFn: () => getAssetPassport(asset!.id),
    enabled: tab === "history" && !!asset,
  });

  const latest = telemetry?.[0];
  const ramPct = latest && latest.ram_total_mb ? (latest.ram_used_mb / latest.ram_total_mb) * 100 : 0;
  const disk = latest?.disks?.[0];
  const diskPct = disk && disk.total_gb ? (disk.used_gb / disk.total_gb) * 100 : 0;

  async function pushUpdate(kb?: string) {
    if (!device) return;
    const what = kb ?? "all pending Windows updates";
    if (!confirm(`Install ${what} on ${device.hostname}? The agent installs in the background and won't reboot.`)) return;
    setBusy(true); setMsg(null);
    try {
      const task = await createRemediation({
        device_id: device.id, action_id: "windows_update_install",
        params: kb ? { kb_article_id: kb } : undefined,
        reason: kb ? `Install ${kb} from portal` : "Install all pending Windows updates from portal",
      });
      await approveRemediation(task.id);
      setMsg({ ok: true, text: `Queued: ${what} will install shortly. Track it under Self-Healing.` });
    } catch (e) { setMsg({ ok: false, text: apiErrorMessage(e, "Couldn't queue the update.") }); }
    finally { setBusy(false); }
  }

  async function assignTo(userId: string) {
    if (!device) return;
    setBusy(true); setMsg(null);
    try {
      if (asset) {
        await updateAsset(asset.id, { assigned_to_user_id: userId || undefined });
      } else {
        // No asset record yet — create one linked to this device so it can be assigned & tracked.
        await createAsset({
          name: device.hostname, category: "laptop", device_id: device.id,
          serial_number: device.serial_number ?? undefined,
          manufacturer: device.manufacturer ?? undefined, model: device.model ?? undefined,
          assigned_to_user_id: userId || undefined,
        });
      }
      await qc.invalidateQueries({ queryKey: ["assets"] });
      setMsg({ ok: true, text: userId ? "Assigned. A receipt email was sent to the employee." : "Unassigned." });
    } catch (e) { setMsg({ ok: false, text: apiErrorMessage(e, "Couldn't update the assignment.") }); }
    finally { setBusy(false); }
  }

  // Open the asset editor. If this device already has an asset record, prefill it; otherwise
  // seed a new one from the device's own telemetry (name/make/model/serial) linked to it.
  function openEditAsset() {
    if (!device) return;
    if (asset) {
      setForm({
        name: asset.name, asset_tag: asset.asset_tag ?? "", category: asset.category, status: asset.status,
        manufacturer: asset.manufacturer ?? "", model: asset.model ?? "", serial_number: asset.serial_number ?? "",
        location: asset.location ?? "", purchase_date: asset.purchase_date ?? "", warranty_expiry: asset.warranty_expiry ?? "",
        purchase_cost: asset.purchase_cost ?? undefined, assigned_to_user_id: asset.assigned_to_user_id ?? undefined,
        device_id: device.id, notes: asset.notes ?? "",
      });
    } else {
      setForm({
        name: [device.manufacturer, device.model].filter(Boolean).join(" ") || device.hostname,
        category: "laptop", status: "in_use", device_id: device.id,
        manufacturer: device.manufacturer ?? "", model: device.model ?? "", serial_number: device.serial_number ?? "",
      });
    }
    setFormError("");
    setEditing(true);
  }

  async function saveAsset(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true); setFormError("");
    // Blank strings → omit; keep numbers as numbers.
    const clean: AssetInput = { name: form.name.trim() };
    for (const [k, v] of Object.entries(form)) {
      if (k === "name") continue;
      if (v === "" || v === undefined || v === null) continue;
      (clean as Record<string, unknown>)[k] = v;
    }
    try {
      if (asset) await updateAsset(asset.id, clean);
      else await createAsset(clean);
      await qc.invalidateQueries({ queryKey: ["assets"] });
      setEditing(false);
      setMsg({ ok: true, text: "Asset details saved." });
    } catch (err) {
      setFormError(apiErrorMessage(err, "Couldn't save the asset. Check the fields and try again."));
    } finally { setSaving(false); }
  }

  async function lockDown() {
    if (!device) return;
    const user = (device.logged_in_user ?? "").split("\\").pop() ?? "";
    const target = prompt("Disable which local Windows account on this device? (signs them out now)", user);
    if (!target) return;
    setBusy(true); setMsg(null);
    try {
      const task = await createRemediation({
        device_id: device.id, action_id: "disable_local_account",
        params: { username: target }, reason: `Disable local account "${target}" (offboarding)`,
      });
      await approveRemediation(task.id);
      setMsg({ ok: true, text: `Locking down "${target}" — they'll be signed out shortly.` });
    } catch (e) { setMsg({ ok: false, text: apiErrorMessage(e, "Couldn't lock down.") }); }
    finally { setBusy(false); }
  }

  async function remove() {
    if (!device || !confirm(`Remove ${device.hostname} from the portal? This deletes its history and can't be undone.`)) return;
    try { await deleteDevice(device.id); window.location.href = "/devices"; }
    catch { alert("Couldn't remove the device."); }
  }

  if (isLoading) return <p className="text-sm" style={{ color: "var(--text-secondary)" }}>Loading…</p>;
  if (!device) return <p className="text-sm" style={{ color: "var(--text-secondary)" }}>Device not found.</p>;

  const userOptions = [{ value: "", label: "— Unassigned —" }, ...(users ?? []).map((u) => ({ value: u.id, label: `${u.full_name} (${u.email})` }))];

  return (
    <div className="space-y-4">
      <Link href="/devices" className="inline-flex items-center gap-1 text-sm" style={{ color: "var(--accent)" }}>
        <ChevronLeft size={15} /> Devices
      </Link>

      <div className="flex items-start justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg" style={{ background: "rgba(154,47,187,0.1)", color: "var(--accent)" }}><Monitor size={20} /></div>
          <div>
            <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>{device.hostname}</h1>
            <p className="text-sm mt-0.5 flex items-center gap-2" style={{ color: "var(--text-secondary)" }}>
              <DeviceStatusBadge status={device.status} /> · {device.os_version} · agent {device.agent_version}
            </p>
          </div>
        </div>
        <div className="flex gap-2 flex-wrap">
          {isStaff && (
            <button onClick={openEditAsset} className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium"
              style={{ background: "var(--surface)", border: "1px solid var(--border)", color: "var(--text-primary)" }}><Pencil size={15} /> Edit details</button>
          )}
          {isAdmin && (<>
            <button onClick={lockDown} disabled={busy} className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium disabled:opacity-50"
              style={{ background: "var(--surface)", border: "1px solid var(--border)", color: "#d97706" }}><UserX size={15} /> Lock down</button>
            <button onClick={remove} className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium"
              style={{ background: "var(--surface)", border: "1px solid var(--border)", color: "#ef4444" }}><Trash2 size={15} /> Remove</button>
          </>)}
        </div>
      </div>

      {msg && <p className="text-sm" style={{ color: msg.ok ? "#10b981" : "#ef4444" }}>{msg.text}</p>}

      <div className="flex gap-4 flex-col md:flex-row">
        {/* Left tab rail (Freshservice-style) */}
        <div className="md:w-48 shrink-0">
          <div className="flex md:flex-col gap-1 overflow-x-auto rounded-xl p-2" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
            {TABS.map((t) => (
              <button key={t.key} onClick={() => setTab(t.key)}
                className="text-left px-3 py-2 rounded-lg text-sm font-medium whitespace-nowrap transition-colors"
                style={{ background: tab === t.key ? "rgba(154,47,187,0.1)" : "transparent", color: tab === t.key ? "var(--accent)" : "var(--text-secondary)" }}>
                {t.label}
              </button>
            ))}
          </div>
        </div>

        <div className="flex-1 min-w-0 rounded-xl p-5" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
          {tab === "overview" && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-x-8">
              <div>
                <h3 className="text-sm font-semibold mb-2" style={{ color: "var(--text-primary)" }}>Device</h3>
                <Row label="Hostname" value={device.hostname} />
                <Row label="OS" value={device.os_version} />
                <Row label="Serial" value={device.serial_number} />
                <Row label="Manufacturer" value={device.manufacturer} />
                <Row label="Model" value={device.model} />
                <Row label="CPU" value={device.cpu_name} />
                <Row label="RAM" value={formatRam(device.total_ram_mb)} />
                <Row label="Storage" value={formatStorage(device.total_storage_gb)} />
                <Row label="Agent version" value={device.agent_version} />
                <Row label="Logged-in user" value={device.logged_in_user} />
                <Row label="Last seen" value={device.last_seen_at ? new Date(device.last_seen_at).toLocaleString() : "—"} />
              </div>
              <div>
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Asset</h3>
                  {isStaff && (
                    <button onClick={openEditAsset} className="inline-flex items-center gap-1 text-xs font-medium hover:underline" style={{ color: "var(--accent)" }}>
                      <Pencil size={12} /> Edit details
                    </button>
                  )}
                </div>
                {asset ? (<>
                  <Row label="Asset tag" value={asset.asset_tag} />
                  <Row label="Category" value={<span className="capitalize">{asset.category}</span>} />
                  <Row label="Status" value={ASSET_STATUS_LABELS[asset.status] ?? asset.status} />
                  <Row label="Location" value={asset.location} />
                  <Row label="Assigned to" value={asset.assigned_to_name} />
                  <Row label="Acknowledged" value={asset.acknowledgement_status} />
                  <Row label="Purchase date" value={asset.purchase_date} />
                  <Row label="Warranty expiry" value={asset.warranty_expiry} />
                  <Row label="Cost" value={asset.purchase_cost != null ? `$${asset.purchase_cost}` : "—"} />
                  <Row label="Notes" value={asset.notes} />
                </>) : (
                  <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
                    No asset record yet. {isStaff ? "Click “Edit details” to set location, warranty, cost and more — it starts tracking this device as an asset." : "Ask an admin to add asset details."}
                  </p>
                )}
              </div>
            </div>
          )}

          {tab === "telemetry" && (latest ? (
            <div className="space-y-3">
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <Gauge label="CPU" value={latest.cpu_percent} sub="Current load" />
                <Gauge label="Memory" value={ramPct} sub={`${(latest.ram_used_mb / 1024).toFixed(1)} / ${(latest.ram_total_mb / 1024).toFixed(1)} GB`} />
                <Gauge label="Disk" value={diskPct} sub={disk ? `${disk.drive} — ${disk.used_gb.toFixed(0)} / ${disk.total_gb.toFixed(0)} GB` : "No disk data"} />
              </div>
              <p className="text-xs" style={{ color: "var(--text-secondary)" }}>Last snapshot: {new Date(latest.collected_at).toLocaleString()}</p>
            </div>
          ) : <p className="text-sm" style={{ color: "var(--text-secondary)" }}>No telemetry received yet.</p>)}

          {tab === "events" && (
            <div className="max-h-[28rem] overflow-y-auto">
            <table className="w-full text-sm"><thead><tr style={{ borderBottom: "1px solid var(--border)" }}>
              {["Level", "Source", "Event", "Message", "When"].map((h) => <th key={h} className="text-left py-2 text-xs uppercase" style={{ color: "var(--text-secondary)" }}>{h}</th>)}
            </tr></thead><tbody>
              {events?.map((e) => <tr key={e.id} style={{ borderBottom: "1px solid var(--border)" }}>
                <td className="py-2 text-xs font-medium" style={{ color: LEVEL_COLOR[e.level] ?? "var(--text-secondary)" }}>{e.level}</td>
                <td className="py-2" style={{ color: "var(--text-primary)" }}>{e.source}</td>
                <td className="py-2" style={{ color: "var(--text-secondary)" }}>{e.event_id}</td>
                <td className="py-2 max-w-md truncate" style={{ color: "var(--text-secondary)" }} title={e.message}>{e.message}</td>
                <td className="py-2 whitespace-nowrap" style={{ color: "var(--text-secondary)" }}>{new Date(e.occurred_at).toLocaleString()}</td></tr>)}
              {!events?.length && <tr><td colSpan={5} className="py-6 text-center" style={{ color: "var(--text-secondary)" }}>No events collected yet.</td></tr>}
            </tbody></table>
            </div>
          )}

          {tab === "software" && (
            <table className="w-full text-sm"><thead><tr style={{ borderBottom: "1px solid var(--border)" }}>
              {["Name", "Version", "Publisher"].map((h) => <th key={h} className="text-left py-2 text-xs uppercase" style={{ color: "var(--text-secondary)" }}>{h}</th>)}
            </tr></thead><tbody>
              {apps?.map((a) => <tr key={a.id} style={{ borderBottom: "1px solid var(--border)" }}>
                <td className="py-2" style={{ color: "var(--text-primary)" }}>{a.name}</td>
                <td className="py-2" style={{ color: "var(--text-secondary)" }}>{a.version ?? "—"}</td>
                <td className="py-2" style={{ color: "var(--text-secondary)" }}>{a.publisher ?? "—"}</td></tr>)}
              {!apps?.length && <tr><td colSpan={3} className="py-6 text-center" style={{ color: "var(--text-secondary)" }}>No apps collected yet.</td></tr>}
            </tbody></table>
          )}

          {tab === "services" && (
            <table className="w-full text-sm"><thead><tr style={{ borderBottom: "1px solid var(--border)" }}>
              {["Display name", "Status", "Startup"].map((h) => <th key={h} className="text-left py-2 text-xs uppercase" style={{ color: "var(--text-secondary)" }}>{h}</th>)}
            </tr></thead><tbody>
              {services?.map((s) => <tr key={s.id} style={{ borderBottom: "1px solid var(--border)" }}>
                <td className="py-2" style={{ color: "var(--text-primary)" }}>{s.display_name}</td>
                <td className="py-2" style={{ color: s.status === "Running" ? "#10b981" : "#64748b" }}>{s.status}</td>
                <td className="py-2" style={{ color: "var(--text-secondary)" }}>{s.start_type}</td></tr>)}
              {!services?.length && <tr><td colSpan={3} className="py-6 text-center" style={{ color: "var(--text-secondary)" }}>No services collected yet.</td></tr>}
            </tbody></table>
          )}

          {tab === "updates" && (
            <div className="space-y-3">
              {isAdmin && updates?.some((u) => !u.is_installed) && (
                <button onClick={() => pushUpdate()} disabled={busy} className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50" style={{ background: "var(--accent)" }}>
                  <DownloadCloud size={15} /> Install all pending
                </button>
              )}
              <table className="w-full text-sm"><thead><tr style={{ borderBottom: "1px solid var(--border)" }}>
                {["KB", "Title", "Status"].map((h) => <th key={h} className="text-left py-2 text-xs uppercase" style={{ color: "var(--text-secondary)" }}>{h}</th>)}
                {isAdmin && <th />}
              </tr></thead><tbody>
                {updates?.map((u) => <tr key={u.id} style={{ borderBottom: "1px solid var(--border)" }}>
                  <td className="py-2 font-medium" style={{ color: "var(--text-primary)" }}>{u.kb_article_id}</td>
                  <td className="py-2 max-w-md truncate" style={{ color: "var(--text-secondary)" }} title={u.title}>{u.title}</td>
                  <td className="py-2 text-xs font-medium" style={{ color: u.is_installed ? "#10b981" : "#f59e0b" }}>{u.is_installed ? "Installed" : "Pending"}</td>
                  {isAdmin && <td className="py-2 text-right">{!u.is_installed && u.kb_article_id && (
                    <button onClick={() => pushUpdate(u.kb_article_id)} disabled={busy} className="text-xs px-2 py-1 rounded-lg" style={{ border: "1px solid var(--border)", color: "var(--accent)" }}>Install</button>
                  )}</td>}
                </tr>)}
                {!updates?.length && <tr><td colSpan={4} className="py-6 text-center" style={{ color: "var(--text-secondary)" }}>No updates collected yet.</td></tr>}
              </tbody></table>
            </div>
          )}

          {tab === "assignment" && (
            <div className="max-w-md space-y-3">
              <div>
                <label className="block text-sm font-medium mb-1" style={{ color: "var(--text-secondary)" }}>Assigned to</label>
                {isAdmin ? (
                  <SearchableSelect value={asset?.assigned_to_user_id ?? ""} onChange={assignTo} placeholder="— Unassigned —" options={userOptions} />
                ) : <p className="text-sm" style={{ color: "var(--text-primary)" }}>{asset?.assigned_to_name ?? "Unassigned"}</p>}
              </div>
              {asset?.assigned_to_name && (
                <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
                  Acknowledgement: <b>{asset.acknowledgement_status}</b>
                  {isAdmin && asset.acknowledgement_status === "pending" && (
                    <button onClick={() => resendAcknowledgement(asset.id).then(() => setMsg({ ok: true, text: "Receipt email re-sent." }))}
                      className="ml-2 underline" style={{ color: "var(--accent)" }}>Re-send email</button>
                  )}
                </p>
              )}
              <p className="text-xs" style={{ color: "var(--text-secondary)" }}>Assigning emails the employee a receipt-confirmation link.</p>
            </div>
          )}

          {tab === "history" && (
            asset ? (
              <div className="space-y-2">
                {passport?.events?.length ? passport.events.map((e) => (
                  <div key={e.id} className="flex gap-3 text-sm py-2 border-b" style={{ borderColor: "var(--border)" }}>
                    <span className="w-40 shrink-0" style={{ color: "var(--text-secondary)" }}>{new Date(e.occurred_at).toLocaleString()}</span>
                    <span style={{ color: "var(--text-primary)" }}>
                      <b className="capitalize">{e.event_type.replace(/_/g, " ")}</b>
                      {e.to_value ? ` → ${e.to_value}` : ""}{e.note ? ` — ${e.note}` : ""}
                      {e.actor_name ? ` (by ${e.actor_name})` : ""}
                    </span>
                  </div>
                )) : <p className="text-sm" style={{ color: "var(--text-secondary)" }}>No history yet.</p>}
              </div>
            ) : <p className="text-sm" style={{ color: "var(--text-secondary)" }}>Assign this device to a user to start tracking its history.</p>
          )}
        </div>
      </div>

      {/* Asset details editor — same fields as the Assets register */}
      {editing && (
        <div className="fixed inset-0 z-50 flex justify-end" style={{ background: "rgba(0,0,0,0.4)" }} onClick={() => setEditing(false)}>
          <form onClick={(e) => e.stopPropagation()} onSubmit={saveAsset}
            className="w-full max-w-md h-full overflow-y-auto p-6 space-y-4"
            style={{ background: "var(--surface)", borderLeft: "1px solid var(--border)" }}>
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>Asset details — {device.hostname}</h2>
              <button type="button" onClick={() => setEditing(false)} style={{ color: "var(--text-secondary)" }}><X size={18} /></button>
            </div>

            <div>
              <label className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>Name *</label>
              <input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
                className="w-full mt-1 px-3 py-2 rounded-lg text-sm outline-none" style={inputStyle} />
            </div>
            <div>
              <label className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>Asset tag</label>
              <input value={form.asset_tag ?? ""} onChange={(e) => setForm({ ...form, asset_tag: e.target.value })}
                className="w-full mt-1 px-3 py-2 rounded-lg text-sm outline-none" style={inputStyle} />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>Category</label>
                <select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value as AssetCategory })}
                  className="w-full mt-1 px-3 py-2 rounded-lg text-sm outline-none capitalize" style={inputStyle}>
                  {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>
              <div>
                <label className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>Status</label>
                <select value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value as AssetStatus })}
                  className="w-full mt-1 px-3 py-2 rounded-lg text-sm outline-none" style={inputStyle}>
                  {STATUSES.map((s) => <option key={s} value={s}>{ASSET_STATUS_LABELS[s] ?? s}</option>)}
                </select>
              </div>
            </div>

            <div>
              <label className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>Assigned to</label>
              <SearchableSelect
                value={form.assigned_to_user_id ?? ""}
                onChange={(v) => setForm({ ...form, assigned_to_user_id: v || undefined })}
                placeholder="— Unassigned —"
                searchPlaceholder="Search by name or email…"
                options={[
                  { value: "", label: "— Unassigned —" },
                  ...(users ?? []).map((u) => ({ value: u.id, label: u.full_name, sublabel: u.email, keywords: u.email })),
                ]}
              />
              <p className="text-xs mt-1" style={{ color: "var(--text-secondary)" }}>Assigning emails the employee a receipt-confirmation link.</p>
            </div>

            <div className="grid grid-cols-2 gap-3">
              {([["manufacturer", "Manufacturer"], ["model", "Model"], ["serial_number", "Serial number"]] as const).map(([key, label]) => (
                <div key={key}>
                  <label className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>{label}</label>
                  <input value={(form[key] as string) ?? ""} onChange={(e) => setForm({ ...form, [key]: e.target.value })}
                    className="w-full mt-1 px-3 py-2 rounded-lg text-sm outline-none" style={inputStyle} />
                </div>
              ))}
              <div>
                <label className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>Location</label>
                <input list="dev-asset-locations" value={form.location ?? ""} placeholder="Pick a location…"
                  onChange={(e) => setForm({ ...form, location: e.target.value })}
                  className="w-full mt-1 px-3 py-2 rounded-lg text-sm outline-none" style={inputStyle} />
                <datalist id="dev-asset-locations">
                  {(managedLocations ?? []).map((l) => <option key={l.id} value={l.name} />)}
                </datalist>
              </div>
            </div>

            <div className="grid grid-cols-3 gap-3">
              <div>
                <label className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>Purchased</label>
                <input type="date" value={form.purchase_date ?? ""} onChange={(e) => setForm({ ...form, purchase_date: e.target.value })}
                  className="w-full mt-1 px-2 py-2 rounded-lg text-sm outline-none" style={inputStyle} />
              </div>
              <div>
                <label className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>Warranty</label>
                <input type="date" value={form.warranty_expiry ?? ""} onChange={(e) => setForm({ ...form, warranty_expiry: e.target.value })}
                  className="w-full mt-1 px-2 py-2 rounded-lg text-sm outline-none" style={inputStyle} />
              </div>
              <div>
                <label className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>Cost</label>
                <input type="number" min="0" step="0.01" value={form.purchase_cost ?? ""}
                  onChange={(e) => setForm({ ...form, purchase_cost: e.target.value ? Number(e.target.value) : undefined })}
                  className="w-full mt-1 px-2 py-2 rounded-lg text-sm outline-none" style={inputStyle} />
              </div>
            </div>

            <div>
              <label className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>Notes</label>
              <textarea value={form.notes ?? ""} onChange={(e) => setForm({ ...form, notes: e.target.value })} rows={3}
                className="w-full mt-1 px-3 py-2 rounded-lg text-sm outline-none resize-none" style={inputStyle} />
            </div>

            {formError && <p className="text-sm text-red-500">{formError}</p>}

            <div className="flex gap-2 pt-2">
              <button type="submit" disabled={saving}
                className="flex-1 px-3 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50"
                style={{ background: "var(--accent)" }}>{saving ? "Saving…" : "Save details"}</button>
              <button type="button" onClick={() => setEditing(false)}
                className="px-3 py-2 rounded-lg text-sm font-medium"
                style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-secondary)" }}>Cancel</button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}

const inputStyle = { background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" } as const;
