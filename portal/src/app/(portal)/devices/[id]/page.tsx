"use client";
import { useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronLeft, Monitor, UserX, Trash2, DownloadCloud, Pencil, X, User, MapPin, Cpu, ShieldCheck, AlertTriangle, Wrench, Check, Minus } from "lucide-react";
import { getDevice, deleteDevice } from "@/lib/api/devices";
import { getDeviceTelemetry, getDeviceEvents, getDeviceApps, getDeviceServices, getDeviceUpdates } from "@/lib/api/device-detail";
import { listAssets, updateAsset, createAsset, getAssetPassport, resendAcknowledgement } from "@/lib/api/assets";
import { getDeviceCompliance } from "@/lib/api/compliance";
import { listUsers } from "@/lib/api/users";
import { listLocations } from "@/lib/api/locations";
import { getMe } from "@/lib/api/auth";
import { createRemediation, approveRemediation } from "@/lib/api/remediation";
import { DeviceStatusBadge } from "@/components/device-status-badge";
import { SearchableSelect } from "@/components/searchable-select";
import { formatRam, formatStorage, apiErrorMessage } from "@/lib/utils";
import { ASSET_STATUS_LABELS, ASSET_STATUS_COLORS } from "@/lib/chart-colors";
import type { AssetInput, AssetCategory, AssetStatus } from "@/lib/api/types";

const CATEGORIES: AssetCategory[] = [
  "laptop", "desktop", "server", "monitor", "phone", "tablet",
  "peripheral", "network", "license", "software", "other",
];
const STATUSES: AssetStatus[] = ["in_use", "in_storage", "in_repair", "retired", "lost"];

// One-click remediations the admin can push to this endpoint. Mirrors the backend
// allowlist (tiers enforced server-side); only parameterless / fixed-param actions
// are exposed here so a push is always a single confident click.
type FixTier = "automatic" | "approval_required" | "admin_only";
type Fix = { id: string; label: string; tier: FixTier; params?: Record<string, string> };
const FIXES: Fix[] = [
  { id: "restart_explorer", label: "Restart Windows Explorer", tier: "automatic" },
  { id: "flush_dns", label: "Flush DNS cache", tier: "automatic" },
  { id: "restart_network_adapter", label: "Restart network adapter", tier: "automatic" },
  { id: "clear_temp", label: "Clear temporary files", tier: "automatic" },
  { id: "clear_system_temp", label: "Deep clean system temp", tier: "automatic" },
  { id: "clear_browser_cache", label: "Clear browser cache", tier: "automatic" },
  { id: "restart_outlook", label: "Restart Outlook", tier: "automatic" },
  { id: "restart_teams", label: "Restart Microsoft Teams", tier: "automatic" },
  { id: "restart_zoom", label: "Restart Zoom", tier: "automatic" },
  { id: "restart_chrome", label: "Restart Google Chrome", tier: "automatic" },
  { id: "restart_edge", label: "Restart Microsoft Edge", tier: "automatic" },
  { id: "restart_service", label: "Restart Print Spooler", tier: "automatic", params: { service_name: "Spooler" } },
  { id: "restart_service", label: "Restart Windows Search", tier: "automatic", params: { service_name: "WSearch" } },
  { id: "restart_service", label: "Restart Audio service", tier: "automatic", params: { service_name: "Audiosrv" } },
  { id: "office_repair", label: "Repair Microsoft Office", tier: "approval_required" },
  { id: "network_reset", label: "Reset network stack", tier: "approval_required" },
  { id: "windows_update_install", label: "Install pending Windows updates", tier: "approval_required" },
  { id: "reset_windows_update_components", label: "Reset Windows Update components", tier: "admin_only" },
];
const TIER_LABEL: Record<FixTier, string> = { automatic: "Automatic", approval_required: "Needs approval", admin_only: "Admin only" };
const TIER_COLOR: Record<FixTier, string> = { automatic: "#10b981", approval_required: "#f59e0b", admin_only: "#ef4444" };

// A fix's stable tag — encodes the service name for restart_service so the three
// spooler/search/audio variants stay distinct.
const fixTag = (f: Fix) => (f.id === "restart_service" ? `restart_service:${f.params?.service_name}` : f.id);

// Map what the event log is showing (its source names) to the fixes most likely to help.
function suggestFixes(sources: string[]): Fix[] {
  const s = sources.join(" ").toLowerCase();
  const rules: [RegExp, string][] = [
    [/spool|print/, "restart_service:Spooler"],
    [/dns|resolver|dnscache/, "flush_dns"],
    [/tcpip|netbt|dhcp|wlan|nic|network|ethernet|lan/, "restart_network_adapter"],
    [/disk|ntfs|volsnap|space|volume/, "clear_system_temp"],
    [/explorer|shell/, "restart_explorer"],
    [/outlook/, "restart_outlook"],
    [/teams/, "restart_teams"],
    [/chrome/, "restart_chrome"],
    [/edge|msedge/, "restart_edge"],
    [/word|excel|powerpnt|office|onenote/, "office_repair"],
    [/windowsupdate|wuau|\bupdate\b/, "windows_update_install"],
    [/search|wsearch|indexer/, "restart_service:WSearch"],
    [/audio|audiosrv|sound/, "restart_service:Audiosrv"],
  ];
  const wanted = new Set(rules.filter(([re]) => re.test(s)).map(([, id]) => id));
  return FIXES.filter((f) => wanted.has(fixTag(f)));
}

type Tab = "overview" | "telemetry" | "events" | "compliance" | "software" | "services" | "updates" | "assignment" | "history";
const TABS: { key: Tab; label: string }[] = [
  { key: "overview", label: "Overview" },
  { key: "telemetry", label: "Telemetry" },
  { key: "events", label: "Health" },
  { key: "compliance", label: "Compliance" },
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
    <div className="flex justify-between gap-4 py-2.5 border-b last:border-0 text-sm" style={{ borderColor: "var(--border)" }}>
      <span style={{ color: "var(--text-secondary)" }}>{label}</span>
      <span className="text-right font-medium" style={{ color: "var(--text-primary)" }}>{value ?? "—"}</span>
    </div>
  );
}

function Pill({ icon: Icon, color, children }: { icon?: typeof User; color?: string; children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1 text-xs font-medium px-2.5 py-1 rounded-full"
      style={{ background: color ? `${color}1a` : "var(--bg)", border: `1px solid ${color ? "transparent" : "var(--border)"}`, color: color ?? "var(--text-secondary)" }}>
      {Icon && <Icon size={12} />}{children}
    </span>
  );
}

function Section({ title, action, children, pad = true }: { title?: string; action?: React.ReactNode; children: React.ReactNode; pad?: boolean }) {
  return (
    <section className="rounded-2xl overflow-hidden" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
      {title && (
        <div className="flex items-center justify-between gap-3 px-5 py-3 border-b" style={{ borderColor: "var(--border)" }}>
          <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>{title}</h3>
          {action}
        </div>
      )}
      <div className={pad ? "p-5" : ""}>{children}</div>
    </section>
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
  const [fixMenu, setFixMenu] = useState(false);

  // Lock down (secure offboarding) modal.
  const [lockOpen, setLockOpen] = useState(false);
  const [lockUser, setLockUser] = useState("");
  const [lockConfirm, setLockConfirm] = useState("");
  const [lockMsg, setLockMsg] = useState<{ ok: boolean; text: string } | null>(null);

  const { data: device, isLoading } = useQuery({ queryKey: ["device", id], queryFn: () => getDevice(id) });
  const { data: telemetry } = useQuery({ queryKey: ["telemetry", id], queryFn: () => getDeviceTelemetry(id), refetchInterval: 30_000 });
  const { data: events } = useQuery({ queryKey: ["dev-events", id], queryFn: () => getDeviceEvents(id), enabled: tab === "events" });
  const { data: compliance } = useQuery({ queryKey: ["dev-compliance", id], queryFn: () => getDeviceCompliance(id), enabled: tab === "compliance" });
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
      await createRemediation({
        device_id: device.id, action_id: "windows_update_install",
        params: kb ? { kb_article_id: kb } : undefined,
        reason: kb ? `Install ${kb} from portal` : "Install all pending Windows updates from portal",
        approve: true,   // the person clicking IS the approver
      });
      setMsg({ ok: true, text: `Queued: ${what} will install shortly. Track it under Self-Healing.` });
    } catch (e) { setMsg({ ok: false, text: apiErrorMessage(e, "Couldn't queue the update.") }); }
    finally { setBusy(false); }
  }

  // Push a one-click remediation to this endpoint (the same createRemediation + approve
  // path the AI engine uses; tiers are still enforced server-side).
  async function runFix(fix: Fix) {
    if (!device) return;
    if (!confirm(`Push "${fix.label}" to ${device.hostname}?\n\nASTRA sends this fix to the endpoint and runs it in the background. Only online devices pick it up immediately.`)) return;
    setBusy(true); setMsg(null); setFixMenu(false);
    try {
      await createRemediation({
        device_id: device.id, action_id: fix.id, params: fix.params,
        reason: `Push "${fix.label}" from device Health (portal)`,
        approve: true,   // the person clicking IS the approver
      });
      setMsg({ ok: true, text: `Queued "${fix.label}" on ${device.hostname}. Track it under Self-Healing.` });
    } catch (e) { setMsg({ ok: false, text: apiErrorMessage(e, "Couldn't push the fix. The device may be offline, or you may lack permission.") }); }
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

  function openLock() {
    if (!device) return;
    // Devices report the user as "DOMAIN\\user"; prefill just the account name.
    setLockUser((device.logged_in_user ?? "").split("\\").pop() ?? "");
    setLockConfirm("");
    setLockMsg(null);
    setLockOpen(true);
  }

  // Secure offboarding: disable (sign out + block sign-in) or re-enable a LOCAL Windows account.
  async function runLock(enable: boolean) {
    if (!device) return;
    const user = lockUser.trim();
    if (!user) { setLockMsg({ ok: false, text: "Enter the local Windows account name." }); return; }
    if (!enable && lockConfirm.trim() !== device.hostname) {
      setLockMsg({ ok: false, text: `Type the device name "${device.hostname}" to confirm.` });
      return;
    }
    setBusy(true); setLockMsg(null);
    try {
      await createRemediation({
        device_id: device.id,
        action_id: enable ? "enable_local_account" : "disable_local_account",
        params: { username: user },
        reason: enable
          ? `Re-enable local account "${user}" (offboarding)`
          : `Disable local account "${user}" and sign out (offboarding)`,
        approve: true,   // the person clicking IS the approver
      });
      setLockMsg({ ok: true, text: enable
        ? `Re-enabling "${user}" on ${device.hostname} — they can sign in again shortly.`
        : `Disabling "${user}" on ${device.hostname} and signing them out. Track it under Self-Healing.` });
    } catch (err) {
      setLockMsg({ ok: false, text: apiErrorMessage(err, "Couldn't queue it. The device may be offline, or you may lack permission.") });
    } finally { setBusy(false); }
  }

  async function remove() {
    if (!device || !confirm(`Remove ${device.hostname} from the portal? This deletes its history and can't be undone.`)) return;
    try { await deleteDevice(device.id); window.location.href = "/devices"; }
    catch { alert("Couldn't remove the device."); }
  }

  if (isLoading) return <p className="text-sm" style={{ color: "var(--text-secondary)" }}>Loading…</p>;
  if (!device) return <p className="text-sm" style={{ color: "var(--text-secondary)" }}>Device not found.</p>;

  const userOptions = [{ value: "", label: "— Unassigned —" }, ...(users ?? []).map((u) => ({ value: u.id, label: `${u.full_name} (${u.email})` }))];
  const stateLabel = asset ? (ASSET_STATUS_LABELS[asset.status] ?? asset.status) : null;
  const stateColor = asset ? (ASSET_STATUS_COLORS[asset.status] ?? "#64748b") : null;

  return (
    <div className="space-y-5">
      <Link href="/devices" className="inline-flex items-center gap-1 text-sm font-medium" style={{ color: "var(--accent)" }}>
        <ChevronLeft size={15} /> Devices
      </Link>

      {/* Header card */}
      <div className="rounded-2xl p-5"
        style={{ border: "1px solid var(--border)", background: "radial-gradient(600px circle at 0% 0%, color-mix(in srgb, var(--accent) 9%, transparent), transparent 60%), var(--surface)" }}>
        <div className="flex items-start justify-between flex-wrap gap-4">
          <div className="flex items-center gap-4 min-w-0">
            <div className="p-3 rounded-2xl shrink-0" style={{ background: "rgba(154,47,187,0.12)", color: "var(--accent)" }}><Monitor size={26} /></div>
            <div className="min-w-0">
              <h1 className="text-2xl font-semibold truncate" style={{ color: "var(--text-primary)" }}>{device.hostname}</h1>
              <div className="flex items-center gap-2 mt-2 flex-wrap">
                <DeviceStatusBadge status={device.status} />
                <Pill icon={Cpu}>{device.os_version}</Pill>
                <Pill>agent {device.agent_version}</Pill>
                {asset?.assigned_to_name && <Pill icon={User}>{asset.assigned_to_name}</Pill>}
                {asset?.location && <Pill icon={MapPin}>{asset.location}</Pill>}
                {stateLabel && stateColor && <Pill color={stateColor}>{stateLabel}</Pill>}
              </div>
            </div>
          </div>
          <div className="flex gap-2 flex-wrap">
            {isStaff && (
              <button onClick={openEditAsset} className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium"
                style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }}><Pencil size={15} /> Edit details</button>
            )}
            {isAdmin && (<>
              <button onClick={openLock} disabled={busy} className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium disabled:opacity-50"
                style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "#d97706" }}><UserX size={15} /> Lock down</button>
              <button onClick={remove} className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium"
                style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "#ef4444" }}><Trash2 size={15} /> Remove</button>
            </>)}
          </div>
        </div>
      </div>

      {msg && <p className="text-sm" style={{ color: msg.ok ? "#10b981" : "#ef4444" }}>{msg.text}</p>}

      {/* Tabs */}
      <div className="flex gap-1 border-b overflow-x-auto" style={{ borderColor: "var(--border)" }}>
        {TABS.map((t) => (
          <button key={t.key} onClick={() => setTab(t.key)}
            className="px-4 py-2.5 text-sm font-medium -mb-px border-b-2 whitespace-nowrap transition-colors"
            style={{ borderColor: tab === t.key ? "var(--accent)" : "transparent", color: tab === t.key ? "var(--accent)" : "var(--text-secondary)" }}>
            {t.label}
          </button>
        ))}
      </div>

      <div className="space-y-4">
          {tab === "overview" && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <Section title="Device">
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
              </Section>
              <Section title="Asset" action={isStaff && (
                <button onClick={openEditAsset} className="inline-flex items-center gap-1 text-xs font-medium hover:underline" style={{ color: "var(--accent)" }}>
                  <Pencil size={12} /> Edit details
                </button>
              )}>
                {asset ? (<>
                  <Row label="Asset tag" value={asset.asset_tag} />
                  <Row label="Category" value={<span className="capitalize">{asset.category}</span>} />
                  <Row label="Status" value={stateLabel} />
                  <Row label="Location" value={asset.location} />
                  <Row label="Assigned to" value={asset.assigned_to_name} />
                  <Row label="Acknowledged" value={<span className="capitalize">{asset.acknowledgement_status.replace(/_/g, " ")}</span>} />
                  <Row label="Purchase date" value={asset.purchase_date} />
                  <Row label="Warranty expiry" value={asset.warranty_expiry} />
                  <Row label="Cost" value={asset.purchase_cost != null ? `$${asset.purchase_cost}` : "—"} />
                  <Row label="Notes" value={asset.notes} />
                </>) : (
                  <div className="flex flex-col items-center text-center py-8 gap-3">
                    <div className="p-3 rounded-2xl" style={{ background: "var(--bg)", color: "var(--text-secondary)" }}><Pencil size={20} /></div>
                    <p className="text-sm max-w-xs" style={{ color: "var(--text-secondary)" }}>
                      No asset record yet — set location, warranty, cost and assignee to start tracking this device as an asset.
                    </p>
                    {isStaff && (
                      <button onClick={openEditAsset} className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium text-white" style={{ background: "var(--accent)" }}>
                        <Pencil size={14} /> Add asset details
                      </button>
                    )}
                  </div>
                )}
              </Section>
            </div>
          )}

          {tab !== "overview" && (
          <Section>
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

          {tab === "events" && (() => {
            const list = events ?? [];
            const critical = list.filter((e) => e.level === "Critical").length;
            const errors = list.filter((e) => e.level === "Error").length;
            const warnings = list.filter((e) => e.level === "Warning").length;
            const healthy = list.length === 0;
            const sources = Object.entries(
              list.reduce<Record<string, number>>((acc, e) => { acc[e.source] = (acc[e.source] ?? 0) + 1; return acc; }, {})
            ).sort((a, b) => b[1] - a[1]).slice(0, 5);
            const suggested = isStaff ? suggestFixes(list.map((e) => e.source)) : [];
            return (
              <div className="space-y-4">
                {/* Health banner — reframes raw errors as ASTRA's proactive monitoring */}
                <div className="rounded-xl p-4 flex items-start gap-3"
                  style={{ background: healthy ? "rgba(16,185,129,0.08)" : "rgba(245,158,11,0.08)", border: `1px solid ${healthy ? "rgba(16,185,129,0.3)" : "rgba(245,158,11,0.3)"}` }}>
                  <div className="p-2 rounded-lg shrink-0" style={{ background: healthy ? "rgba(16,185,129,0.15)" : "rgba(245,158,11,0.15)", color: healthy ? "#10b981" : "#f59e0b" }}>
                    {healthy ? <ShieldCheck size={18} /> : <AlertTriangle size={18} />}
                  </div>
                  <div className="min-w-0">
                    <p className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
                      {healthy ? "Healthy — no issues detected" : `ASTRA detected ${list.length} issue${list.length === 1 ? "" : "s"} in the last 24 hours`}
                    </p>
                    <p className="text-xs mt-0.5" style={{ color: "var(--text-secondary)" }}>
                      {healthy
                        ? "This device is being actively monitored. No errors or critical events in the last 24 hours."
                        : "Surfaced automatically so IT can act before users notice — many of these are auto-remediated under Self-Healing."}
                    </p>
                    {!healthy && (
                      <div className="flex gap-2 mt-2 flex-wrap">
                        {critical > 0 && <Pill color="#ef4444">{critical} critical</Pill>}
                        {errors > 0 && <Pill color="#f97316">{errors} error{errors === 1 ? "" : "s"}</Pill>}
                        {warnings > 0 && <Pill color="#f59e0b">{warnings} warning{warnings === 1 ? "" : "s"}</Pill>}
                      </div>
                    )}
                  </div>
                </div>

                {/* Fix actions — push a remediation to this endpoint */}
                {isStaff && (
                  <div className="rounded-xl p-4" style={{ background: "var(--bg)", border: "1px solid var(--border)" }}>
                    <div className="flex items-center justify-between gap-3 flex-wrap">
                      <div>
                        <p className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Push a fix to this device</p>
                        <p className="text-xs mt-0.5" style={{ color: "var(--text-secondary)" }}>ASTRA runs it on the endpoint in the background. Tracked under Self-Healing.</p>
                      </div>
                      <button onClick={() => setFixMenu(true)} disabled={busy}
                        className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50 shrink-0" style={{ background: "var(--accent)" }}>
                        <Wrench size={15} /> Run a fix…
                      </button>
                    </div>
                    {suggested.length > 0 && (
                      <div className="mt-3 pt-3 border-t" style={{ borderColor: "var(--border)" }}>
                        <p className="text-xs font-medium mb-2" style={{ color: "var(--text-secondary)" }}>Suggested for what we&apos;re seeing</p>
                        <div className="flex gap-2 flex-wrap">
                          {suggested.map((f) => (
                            <button key={fixTag(f)} onClick={() => runFix(f)} disabled={busy}
                              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium disabled:opacity-50"
                              style={{ background: "var(--surface)", border: "1px solid var(--border)", color: "var(--accent)" }}>
                              <Wrench size={12} /> {f.label}
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {sources.length > 0 && (
                  <div>
                    <p className="text-xs font-medium mb-2" style={{ color: "var(--text-secondary)" }}>Most frequent sources</p>
                    <div className="space-y-1.5">
                      {sources.map(([src, n]) => (
                        <div key={src} className="flex items-center justify-between text-sm gap-3">
                          <span className="truncate" style={{ color: "var(--text-primary)" }}>{src}</span>
                          <span className="text-xs font-medium px-2 py-0.5 rounded-full shrink-0" style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-secondary)" }}>{n}×</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {list.length > 0 && (
                  <div>
                    <p className="text-xs font-medium mb-2" style={{ color: "var(--text-secondary)" }}>Recent diagnostic events (last 24h)</p>
                    <div className="max-h-[22rem] overflow-y-auto rounded-lg" style={{ border: "1px solid var(--border)" }}>
                      <table className="w-full text-sm"><thead><tr style={{ borderBottom: "1px solid var(--border)" }}>
                        {["Level", "Source", "Event", "Message", "When"].map((h) => <th key={h} className="text-left px-3 py-2 text-xs uppercase" style={{ color: "var(--text-secondary)" }}>{h}</th>)}
                      </tr></thead><tbody>
                        {list.map((e) => <tr key={e.id} style={{ borderBottom: "1px solid var(--border)" }}>
                          <td className="px-3 py-2 text-xs font-medium" style={{ color: LEVEL_COLOR[e.level] ?? "var(--text-secondary)" }}>{e.level}</td>
                          <td className="px-3 py-2" style={{ color: "var(--text-primary)" }}>{e.source}</td>
                          <td className="px-3 py-2" style={{ color: "var(--text-secondary)" }}>{e.event_id}</td>
                          <td className="px-3 py-2 max-w-md truncate" style={{ color: "var(--text-secondary)" }} title={e.message}>{e.message}</td>
                          <td className="px-3 py-2 whitespace-nowrap" style={{ color: "var(--text-secondary)" }}>{new Date(e.occurred_at).toLocaleString()}</td></tr>)}
                      </tbody></table>
                    </div>
                  </div>
                )}
              </div>
            );
          })()}

          {tab === "compliance" && (
            <div className="space-y-2">
              {compliance?.checks.map((c) => {
                const color = c.status === "pass" ? "#10b981" : c.status === "fail" ? "#ef4444" : "#64748b";
                return (
                  <div key={c.key} className="flex items-center justify-between gap-3 py-2.5 border-b last:border-0" style={{ borderColor: "var(--border)" }}>
                    <div className="flex items-center gap-3 min-w-0">
                      <span className="p-1 rounded-full shrink-0" style={{ background: `${color}1a`, color }}>
                        {c.status === "pass" ? <Check size={13} /> : c.status === "fail" ? <X size={13} /> : <Minus size={13} />}
                      </span>
                      <div className="min-w-0">
                        <p className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>{c.label}</p>
                        <p className="text-xs" style={{ color: "var(--text-secondary)" }}>{c.detail}</p>
                      </div>
                    </div>
                    {isStaff && c.status === "fail" && c.fix_action_id && (
                      <button onClick={() => runFix({ id: c.fix_action_id!, label: c.label, tier: "approval_required" })} disabled={busy}
                        className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium disabled:opacity-50 shrink-0"
                        style={{ background: "var(--surface)", border: "1px solid var(--border)", color: "var(--accent)" }}>
                        <Wrench size={12} /> Fix
                      </button>
                    )}
                  </div>
                );
              })}
              {!compliance?.checks?.length && <p className="text-sm" style={{ color: "var(--text-secondary)" }}>No compliance data yet — the device needs to report telemetry first.</p>}
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
              {isAdmin && (
                <div className="flex items-center justify-between gap-3 flex-wrap rounded-lg p-3" style={{ background: "var(--bg)", border: "1px solid var(--border)" }}>
                  <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
                    Push Windows Updates to this device. The agent installs everything pending in the background and won&apos;t reboot.
                    {(() => { const n = updates?.filter((u) => !u.is_installed).length ?? 0; return n > 0 ? ` ${n} pending in the last scan.` : ""; })()}
                  </p>
                  <button onClick={() => pushUpdate()} disabled={busy} className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50 shrink-0" style={{ background: "var(--accent)" }}>
                    <DownloadCloud size={15} /> Install all pending
                  </button>
                </div>
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
          </Section>
          )}
      </div>

      {/* Run a fix — pick a remediation to push to this endpoint */}
      {fixMenu && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: "rgba(0,0,0,0.5)" }}
          onClick={() => setFixMenu(false)}>
          <div className="w-full max-w-lg rounded-xl p-5 max-h-[85vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}
            style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
            <div className="flex items-start justify-between gap-3 mb-1">
              <div>
                <h2 className="text-base font-semibold" style={{ color: "var(--text-primary)" }}>Push a fix to {device.hostname}</h2>
                <p className="text-xs mt-0.5" style={{ color: "var(--text-secondary)" }}>
                  ASTRA sends the fix to the endpoint and runs it in the background. Every push is approved by you and audit-logged.
                </p>
              </div>
              <button onClick={() => setFixMenu(false)} style={{ color: "var(--text-secondary)" }}><X size={18} /></button>
            </div>

            <div className="mt-3 space-y-1.5">
              {FIXES.filter((f) => f.tier !== "admin_only" || isAdmin).map((f) => (
                <button key={fixTag(f)} onClick={() => runFix(f)} disabled={busy}
                  className="w-full flex items-center justify-between gap-3 px-3 py-2.5 rounded-lg text-left transition-colors hover:bg-brand-500/5 disabled:opacity-50"
                  style={{ border: "1px solid var(--border)", background: "var(--bg)" }}>
                  <span className="flex items-center gap-2 min-w-0">
                    <Wrench size={14} style={{ color: "var(--accent)" }} className="shrink-0" />
                    <span className="text-sm font-medium truncate" style={{ color: "var(--text-primary)" }}>{f.label}</span>
                  </span>
                  <span className="text-[11px] font-medium px-2 py-0.5 rounded-full shrink-0"
                    style={{ color: TIER_COLOR[f.tier], background: `${TIER_COLOR[f.tier]}1a` }}>{TIER_LABEL[f.tier]}</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Lock down — secure offboarding: disable / re-enable a local Windows account */}
      {lockOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: "rgba(0,0,0,0.5)" }}
          onClick={() => !busy && setLockOpen(false)}>
          <div className="w-full max-w-md rounded-xl p-5" onClick={(e) => e.stopPropagation()}
            style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
            <div className="flex items-start justify-between gap-3 mb-3">
              <div className="flex items-center gap-2">
                <div className="p-2 rounded-lg" style={{ background: "rgba(217,119,6,0.12)", color: "#d97706" }}><UserX size={18} /></div>
                <div>
                  <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Lock down — {device.hostname}</h2>
                  <p className="text-xs" style={{ color: "var(--text-secondary)" }}>Disable or re-enable this device&apos;s local account.</p>
                </div>
              </div>
              <button onClick={() => !busy && setLockOpen(false)} style={{ color: "var(--text-secondary)" }}><X size={16} /></button>
            </div>

            <label className="block text-xs font-medium mb-1" style={{ color: "var(--text-secondary)" }}>Local account name</label>
            <input value={lockUser} onChange={(e) => setLockUser(e.target.value)}
              placeholder="the employee's Windows username"
              className="w-full px-3 py-2 rounded-lg text-sm outline-none focus:ring-2 focus:ring-brand-500 mb-3"
              style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }} />

            <div className="rounded-lg p-3 text-xs mb-3 space-y-1" style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-secondary)" }}>
              <p><b>Disable</b> signs the user out now and blocks future sign-in. The password is <b>not</b> changed and <b>nothing is deleted</b> — fully reversible with Re-enable.</p>
              <p>Works on <b>local</b> Windows accounts only; domain/Entra accounts are managed in AD/Intune.</p>
            </div>

            <label className="block text-xs font-medium mb-1" style={{ color: "var(--text-secondary)" }}>
              Type <span className="font-mono" style={{ color: "var(--text-primary)" }}>{device.hostname}</span> to confirm disabling
            </label>
            <input value={lockConfirm} onChange={(e) => setLockConfirm(e.target.value)}
              className="w-full px-3 py-2 rounded-lg text-sm outline-none focus:ring-2 focus:ring-brand-500 mb-3"
              style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }} />

            {lockMsg && <p className="text-xs mb-3" style={{ color: lockMsg.ok ? "#10b981" : "#ef4444" }}>{lockMsg.text}</p>}

            <div className="flex items-center justify-between gap-2">
              <button onClick={() => runLock(true)} disabled={busy}
                className="px-3 py-2 rounded-lg text-sm font-medium disabled:opacity-50"
                style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }}>
                Re-enable account
              </button>
              <button onClick={() => runLock(false)} disabled={busy}
                className="px-3 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50"
                style={{ background: "#dc2626" }}>
                {busy ? "Working…" : "Disable & sign out"}
              </button>
            </div>
          </div>
        </div>
      )}

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
