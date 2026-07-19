"use client";
import { useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Package, Plus, Trash2, Pencil, X, MailCheck, Mail, Clock } from "lucide-react";
import { assetLocation, UNASSIGNED_LOCATION } from "@/lib/asset-filters";
import {
  listAssets, getAssetSummary, createAsset, updateAsset, deleteAsset, resendAcknowledgement,
} from "@/lib/api/assets";
import { listUsers } from "@/lib/api/users";
import { getDevices } from "@/lib/api/dashboard";
import { getMe } from "@/lib/api/auth";
import { SearchableSelect } from "@/components/searchable-select";
import type { Asset, AssetCategory, AssetStatus, AssetInput } from "@/lib/api/types";

const CATEGORIES: AssetCategory[] = [
  "laptop", "desktop", "server", "monitor", "phone", "tablet",
  "peripheral", "network", "license", "software", "other",
];
const STATUSES: AssetStatus[] = ["in_use", "in_storage", "in_repair", "retired", "lost"];

const STATUS_STYLE: Record<AssetStatus, { label: string; color: string }> = {
  in_use: { label: "In use", color: "#10b981" },
  in_storage: { label: "In storage", color: "#3b82f6" },
  in_repair: { label: "In repair", color: "#f59e0b" },
  retired: { label: "Retired", color: "#64748b" },
  lost: { label: "Lost", color: "#ef4444" },
};

const EMPTY: AssetInput = { name: "", category: "laptop", status: "in_use" };

const money = (n: number) =>
  n.toLocaleString(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 0 });

function Card({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return (
    <div className="rounded-xl p-4" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
      <p className="text-xs uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>{label}</p>
      <p className="text-2xl font-semibold mt-1" style={{ color: accent ?? "var(--text-primary)" }}>{value}</p>
    </div>
  );
}

export default function AssetsPage() {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<Asset | "new" | null>(null);
  const [form, setForm] = useState<AssetInput>(EMPTY);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const { data: me } = useQuery({ queryKey: ["me"], queryFn: getMe });
  const { data: assets, isLoading } = useQuery({ queryKey: ["assets"], queryFn: listAssets });
  const { data: summary } = useQuery({ queryKey: ["asset-summary"], queryFn: getAssetSummary });
  const { data: users } = useQuery({ queryKey: ["users"], queryFn: listUsers });
  const { data: devices } = useQuery({ queryKey: ["devices"], queryFn: getDevices });
  const isStaff = me?.role === "admin" || me?.role === "technician";

  const [locFilter, setLocFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState<"all" | AssetStatus>("all");
  const locations = useMemo(
    () => Array.from(new Set((assets ?? []).map(assetLocation))).sort((a, b) => a.localeCompare(b)),
    [assets],
  );
  const visible = useMemo(
    () => (assets ?? []).filter(
      (a) => (locFilter === "all" || assetLocation(a) === locFilter)
        && (statusFilter === "all" || a.status === statusFilter),
    ),
    [assets, locFilter, statusFilter],
  );

  function openNew() { setForm(EMPTY); setError(""); setEditing("new"); }
  function openEdit(a: Asset) {
    setForm({
      name: a.name, asset_tag: a.asset_tag ?? "", category: a.category, status: a.status,
      manufacturer: a.manufacturer ?? "", model: a.model ?? "", serial_number: a.serial_number ?? "",
      location: a.location ?? "", purchase_date: a.purchase_date ?? "", warranty_expiry: a.warranty_expiry ?? "",
      purchase_cost: a.purchase_cost ?? undefined, assigned_to_user_id: a.assigned_to_user_id ?? undefined,
      device_id: a.device_id ?? undefined, notes: a.notes ?? "",
    });
    setError("");
    setEditing(a);
  }

  async function refresh() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["assets"] }),
      queryClient.invalidateQueries({ queryKey: ["asset-summary"] }),
    ]);
  }

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError("");
    // Blank strings → omit; numbers stay numbers.
    const clean: AssetInput = { name: form.name.trim() };
    for (const [k, v] of Object.entries(form)) {
      if (k === "name") continue;
      if (v === "" || v === undefined || v === null) continue;
      (clean as Record<string, unknown>)[k] = v;
    }
    try {
      if (editing === "new") await createAsset(clean);
      else if (editing) await updateAsset(editing.id, clean);
      setEditing(null);
      await refresh();
    } catch {
      setError("Couldn't save the asset. Check the fields and try again.");
    } finally {
      setSaving(false);
    }
  }

  async function remove(id: string) {
    await deleteAsset(id);
    await refresh();
  }

  async function resend(id: string) {
    try {
      await resendAcknowledgement(id);
      await refresh();
      alert("Acknowledgement email re-sent to the assignee.");
    } catch {
      alert("Couldn't re-send. The asset may not be assigned, or email isn't set up yet.");
    }
  }

  // Linking a device auto-fills the make/model/serial (and the name, if blank) from its telemetry.
  function selectDevice(id: string) {
    const d = devices?.find((x) => x.id === id);
    setForm((f) => ({
      ...f,
      device_id: id || undefined,
      ...(d
        ? {
            manufacturer: d.manufacturer ?? f.manufacturer,
            model: d.model ?? f.model,
            serial_number: d.serial_number ?? f.serial_number,
            name: f.name && f.name.trim()
              ? f.name
              : [d.manufacturer, d.model].filter(Boolean).join(" ") || d.hostname,
          }
        : {}),
    }));
  }

  const inputStyle = {
    background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)",
  } as const;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="p-2 rounded-lg" style={{ background: "rgba(37,99,235,0.1)", color: "var(--accent)" }}>
            <Package size={18} />
          </div>
          <div>
            <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>Assets</h1>
            <p className="text-sm mt-0.5" style={{ color: "var(--text-secondary)" }}>
              Your IT asset register — hardware, licenses and peripherals
            </p>
          </div>
        </div>
        {isStaff && (
          <button onClick={openNew}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium text-white"
            style={{ background: "var(--accent)" }}>
            <Plus size={16} /> Add asset
          </button>
        )}
      </div>

      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card label="Total assets" value={String(summary.total)} />
          <Card label="Total value" value={money(summary.total_value)} />
          <Card label="In repair" value={String(summary.by_status["in_repair"] ?? 0)} accent="#f59e0b" />
          <Card label="Warranty <60d" value={String(summary.warranty_expiring_soon)}
            accent={summary.warranty_expiring_soon > 0 ? "#ef4444" : undefined} />
        </div>
      )}

      {/* Filters — slice the register by location and status */}
      <div className="flex items-center gap-2 flex-wrap">
        <select value={locFilter} onChange={(e) => setLocFilter(e.target.value)}
          className="px-3 py-2 rounded-lg text-sm font-medium outline-none"
          style={{ background: locFilter !== "all" ? "rgba(37,99,235,0.1)" : "var(--surface)", border: "1px solid var(--border)", color: locFilter !== "all" ? "var(--accent)" : "var(--text-primary)" }}>
          <option value="all">All locations</option>
          {locations.map((l) => <option key={l} value={l}>{l}</option>)}
        </select>
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value as "all" | AssetStatus)}
          className="px-3 py-2 rounded-lg text-sm font-medium outline-none"
          style={{ background: statusFilter !== "all" ? "rgba(37,99,235,0.1)" : "var(--surface)", border: "1px solid var(--border)", color: statusFilter !== "all" ? "var(--accent)" : "var(--text-primary)" }}>
          <option value="all">All statuses</option>
          {STATUSES.map((s) => <option key={s} value={s}>{STATUS_STYLE[s].label}</option>)}
        </select>
        <span className="text-xs" style={{ color: "var(--text-secondary)" }}>{visible.length} of {assets?.length ?? 0}</span>
      </div>

      <div className="rounded-xl overflow-hidden" style={{ border: "1px solid var(--border)" }}>
        <div className="overflow-x-auto" style={{ background: "var(--surface)" }}>
          <table className="w-full text-sm whitespace-nowrap">
            <thead>
              <tr style={{ borderBottom: "1px solid var(--border)" }}>
                {["Tag", "Name", "Category", "Status", "Assigned to", "Location", "Device", "Serial", "Value", "Warranty", ""].map((h) => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide"
                    style={{ color: "var(--text-secondary)" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {isLoading && <tr><td colSpan={11} className="px-4 py-8 text-center" style={{ color: "var(--text-secondary)" }}>Loading…</td></tr>}
              {!isLoading && !assets?.length && (
                <tr><td colSpan={11} className="px-4 py-10 text-center" style={{ color: "var(--text-secondary)" }}>
                  No assets yet. {isStaff ? "Click “Add asset” to register one." : ""}
                </td></tr>
              )}
              {!isLoading && !!assets?.length && !visible.length && (
                <tr><td colSpan={11} className="px-4 py-10 text-center" style={{ color: "var(--text-secondary)" }}>No assets match these filters.</td></tr>
              )}
              {visible.map((a) => (
                <tr key={a.id} style={{ borderBottom: "1px solid var(--border)" }}>
                  <td className="px-4 py-3" style={{ color: "var(--text-secondary)" }}>{a.asset_tag ?? "—"}</td>
                  <td className="px-4 py-3 font-medium" style={{ color: "var(--text-primary)" }}>{a.name}</td>
                  <td className="px-4 py-3 capitalize" style={{ color: "var(--text-secondary)" }}>{a.category}</td>
                  <td className="px-4 py-3">
                    <span className="text-xs font-medium px-2 py-0.5 rounded-full"
                      style={{ color: STATUS_STYLE[a.status].color, background: `${STATUS_STYLE[a.status].color}1a` }}>
                      {STATUS_STYLE[a.status].label}
                    </span>
                  </td>
                  <td className="px-4 py-3" style={{ color: "var(--text-secondary)" }}>
                    {a.assigned_to_name ?? "—"}
                    {a.assigned_to_name && a.acknowledgement_status === "acknowledged" && (
                      <span className="ml-1.5 inline-flex items-center gap-0.5 text-xs" style={{ color: "#10b981" }}
                        title={a.acknowledged_at ? `Acknowledged ${new Date(a.acknowledged_at).toLocaleString()}` : "Acknowledged"}>
                        <MailCheck size={12} /> Acknowledged
                      </span>
                    )}
                    {a.assigned_to_name && a.acknowledgement_status === "pending" && (
                      <span className="ml-1.5 inline-flex items-center gap-0.5 text-xs" style={{ color: "#f59e0b" }}
                        title="Waiting for the assignee to confirm receipt">
                        <Clock size={12} /> Awaiting receipt
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3" style={{ color: "var(--text-secondary)" }}>{a.location ?? "—"}</td>
                  <td className="px-4 py-3" style={{ color: "var(--text-secondary)" }}>{a.device_hostname ?? "—"}</td>
                  <td className="px-4 py-3" style={{ color: "var(--text-secondary)" }}>{a.serial_number ?? "—"}</td>
                  <td className="px-4 py-3" style={{ color: "var(--text-secondary)" }}>{a.purchase_cost != null ? money(a.purchase_cost) : "—"}</td>
                  <td className="px-4 py-3" style={{ color: "var(--text-secondary)" }}>{a.warranty_expiry ?? "—"}</td>
                  <td className="px-4 py-3 text-right">
                    {isStaff && (
                      <div className="flex gap-1 justify-end">
                        {a.acknowledgement_status === "pending" && a.assigned_to_user_id && (
                          <button onClick={() => resend(a.id)} title="Re-send acknowledgement email"
                            className="p-1 rounded-lg hover:bg-blue-500/10 hover:text-blue-500" style={{ color: "var(--text-secondary)" }}>
                            <Mail size={14} />
                          </button>
                        )}
                        <button onClick={() => openEdit(a)} title="Edit"
                          className="p-1 rounded-lg hover:bg-blue-500/10 hover:text-blue-500" style={{ color: "var(--text-secondary)" }}>
                          <Pencil size={14} />
                        </button>
                        <button onClick={() => remove(a.id)} title="Delete"
                          className="p-1 rounded-lg hover:bg-red-500/10 hover:text-red-500" style={{ color: "var(--text-secondary)" }}>
                          <Trash2 size={14} />
                        </button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Create / edit drawer */}
      {editing && (
        <div className="fixed inset-0 z-50 flex justify-end" style={{ background: "rgba(0,0,0,0.4)" }}
          onClick={() => setEditing(null)}>
          <form onClick={(e) => e.stopPropagation()} onSubmit={save}
            className="w-full max-w-md h-full overflow-y-auto p-6 space-y-4"
            style={{ background: "var(--surface)", borderLeft: "1px solid var(--border)" }}>
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>
                {editing === "new" ? "Add asset" : "Edit asset"}
              </h2>
              <button type="button" onClick={() => setEditing(null)} style={{ color: "var(--text-secondary)" }}>
                <X size={18} />
              </button>
            </div>

            {([
              ["name", "Name *", "text"],
              ["asset_tag", "Asset tag", "text"],
            ] as const).map(([key, label, type]) => (
              <div key={key}>
                <label className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>{label}</label>
                <input type={type} required={key === "name"} value={(form[key] as string) ?? ""}
                  onChange={(e) => setForm({ ...form, [key]: e.target.value })}
                  className="w-full mt-1 px-3 py-2 rounded-lg text-sm outline-none" style={inputStyle} />
              </div>
            ))}

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
                  {STATUSES.map((s) => <option key={s} value={s}>{STATUS_STYLE[s].label}</option>)}
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
                  ...(users ?? []).map((u) => ({
                    value: u.id, label: u.full_name, sublabel: u.email, keywords: u.email,
                  })),
                ]}
              />
            </div>

            <div>
              <label className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>Linked device</label>
              <SearchableSelect
                value={form.device_id ?? ""}
                onChange={selectDevice}
                placeholder="— None —"
                searchPlaceholder="Search by hostname or serial number…"
                options={[
                  { value: "", label: "— None —" },
                  ...(devices ?? []).map((d) => ({
                    value: d.id,
                    label: d.hostname,
                    sublabel: [
                      [d.manufacturer, d.model].filter(Boolean).join(" "),
                      d.serial_number ? `SN ${d.serial_number}` : null,
                      d.logged_in_user ? `user ${d.logged_in_user}` : null,
                    ].filter(Boolean).join(" · "),
                    keywords: [d.serial_number, d.manufacturer, d.model, d.logged_in_user, d.os_version]
                      .filter(Boolean).join(" "),
                  })),
                ]}
              />
              <p className="text-xs mt-1" style={{ color: "var(--text-secondary)" }}>
                Linking a device auto-fills its make, model and serial number.
              </p>
            </div>

            <div className="grid grid-cols-2 gap-3">
              {([
                ["manufacturer", "Manufacturer"], ["model", "Model"],
                ["serial_number", "Serial number"],
              ] as const).map(([key, label]) => (
                <div key={key}>
                  <label className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>{label}</label>
                  <input value={(form[key] as string) ?? ""} onChange={(e) => setForm({ ...form, [key]: e.target.value })}
                    className="w-full mt-1 px-3 py-2 rounded-lg text-sm outline-none" style={inputStyle} />
                </div>
              ))}
              <div>
                <label className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>Location</label>
                <input list="asset-locations" value={form.location ?? ""} placeholder="Pick or add a location…"
                  onChange={(e) => setForm({ ...form, location: e.target.value })}
                  className="w-full mt-1 px-3 py-2 rounded-lg text-sm outline-none" style={inputStyle} />
                <datalist id="asset-locations">
                  {locations.filter((l) => l !== UNASSIGNED_LOCATION).map((l) => <option key={l} value={l} />)}
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

            {error && <p className="text-sm text-red-500">{error}</p>}

            <div className="flex gap-2 pt-2">
              <button type="submit" disabled={saving}
                className="flex-1 px-3 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50"
                style={{ background: "var(--accent)" }}>{saving ? "Saving…" : "Save asset"}</button>
              <button type="button" onClick={() => setEditing(null)}
                className="px-3 py-2 rounded-lg text-sm font-medium"
                style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-secondary)" }}>Cancel</button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
