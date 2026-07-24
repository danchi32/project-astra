"use client";
import { useState } from "react";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Zap, Plus, Trash2 } from "lucide-react";
import { getMe } from "@/lib/api/auth";
import {
  listRemediationActions, listGlobalFixes, createGlobalFix, deleteGlobalFix,
} from "@/lib/api/platform";

export default function GlobalFixesPage() {
  const queryClient = useQueryClient();
  const { data: me } = useQuery({ queryKey: ["me"], queryFn: getMe });
  const enabled = !!me?.is_platform_admin;
  const { data: actions } = useQuery({ queryKey: ["remediation-actions"], queryFn: listRemediationActions, enabled });
  const { data: fixes, isLoading } = useQuery({ queryKey: ["global-fixes"], queryFn: listGlobalFixes, enabled });

  const [problem, setProblem] = useState("");
  const [actionId, setActionId] = useState("");
  const [param, setParam] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const selected = actions?.find((a) => a.id === actionId);
  const needsProcess = selected?.params.includes("process_name");
  const needsService = selected?.params.includes("service_name");

  async function refresh() { await queryClient.invalidateQueries({ queryKey: ["global-fixes"] }); }

  async function add(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true); setError("");
    try {
      await createGlobalFix({
        problem: problem.trim(),
        action_id: actionId,
        process_name: needsProcess ? param.trim() || undefined : undefined,
        service_name: needsService ? param.trim() || undefined : undefined,
      });
      setProblem(""); setActionId(""); setParam("");
      await refresh();
    } catch {
      setError("Couldn't save. Check the problem text and action (allowlisted app/service names only).");
    } finally { setSaving(false); }
  }
  async function remove(id: string) {
    if (!confirm("Remove this global auto-fix for all organizations?")) return;
    await deleteGlobalFix(id);
    await refresh();
  }

  if (me && !me.is_platform_admin) {
    return <p className="text-sm" style={{ color: "var(--text-secondary)" }}>Platform administrator access required.</p>;
  }

  const inputStyle = { background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" } as const;

  return (
    <div className="space-y-6">
      <Link href="/platform" className="inline-flex items-center gap-1.5 text-sm" style={{ color: "var(--text-secondary)" }}>
        <ArrowLeft size={15} /> Platform
      </Link>

      <div className="flex items-center gap-2">
        <div className="p-2 rounded-lg" style={{ background: "rgba(154,47,187,0.1)", color: "var(--accent)" }}>
          <Zap size={18} />
        </div>
        <div>
          <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>Global auto-fixes</h1>
          <p className="text-sm mt-0.5" style={{ color: "var(--text-secondary)" }}>
            When any org&apos;s user reports a matching problem, the assistant applies the action <span className="font-medium">automatically</span> — for every organization, no AI call.
          </p>
        </div>
      </div>

      <form onSubmit={add} className="rounded-xl p-4 space-y-3" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
        <div>
          <label className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>When the user says (problem)</label>
          <input required value={problem} onChange={(e) => setProblem(e.target.value)}
            placeholder="e.g. the shared network drive keeps disconnecting"
            className="w-full mt-1 px-3 py-2 rounded-lg text-sm outline-none focus:ring-2 focus:ring-brand-500" style={inputStyle} />
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <label className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>Apply this action</label>
            <select required value={actionId} onChange={(e) => { setActionId(e.target.value); setParam(""); }}
              className="w-full mt-1 px-3 py-2 rounded-lg text-sm outline-none" style={inputStyle}>
              <option value="">Select an action…</option>
              {actions?.map((a) => <option key={a.id} value={a.id}>{a.label} ({a.tier})</option>)}
            </select>
          </div>
          {(needsProcess || needsService) && (
            <div>
              <label className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>
                {needsProcess ? "App process (e.g. EXCEL)" : "Service (e.g. Spooler)"}
              </label>
              <input required value={param} onChange={(e) => setParam(e.target.value)}
                className="w-full mt-1 px-3 py-2 rounded-lg text-sm outline-none focus:ring-2 focus:ring-brand-500" style={inputStyle} />
            </div>
          )}
        </div>
        {error && <p className="text-sm text-red-500">{error}</p>}
        <button type="submit" disabled={saving}
          className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50"
          style={{ background: "var(--accent)" }}>
          <Plus size={15} /> {saving ? "Saving…" : "Add auto-fix for all organizations"}
        </button>
      </form>

      <div className="rounded-xl overflow-hidden" style={{ border: "1px solid var(--border)" }}>
        <div className="overflow-x-auto" style={{ background: "var(--surface)" }}>
          <table className="w-full text-sm whitespace-nowrap">
            <thead><tr style={{ borderBottom: "1px solid var(--border)" }}>
              {["Problem", "Auto-applies", "Target", "Added", ""].map((h) => (
                <th key={h} className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {isLoading && <tr><td colSpan={5} className="px-4 py-8 text-center" style={{ color: "var(--text-secondary)" }}>Loading…</td></tr>}
              {!isLoading && !fixes?.length && (
                <tr><td colSpan={5} className="px-4 py-10 text-center" style={{ color: "var(--text-secondary)" }}>No global auto-fixes yet.</td></tr>
              )}
              {fixes?.map((f) => (
                <tr key={f.id} style={{ borderBottom: "1px solid var(--border)" }}>
                  <td className="px-4 py-3 max-w-[360px] truncate" style={{ color: "var(--text-primary)" }} title={f.problem}>{f.problem}</td>
                  <td className="px-4 py-3" style={{ color: "var(--text-secondary)" }}>{f.action_label}</td>
                  <td className="px-4 py-3 font-mono text-xs" style={{ color: "var(--text-secondary)" }}>
                    {f.params ? Object.values(f.params).join(", ") : "—"}
                  </td>
                  <td className="px-4 py-3" style={{ color: "var(--text-secondary)" }}>{new Date(f.created_at).toLocaleDateString()}</td>
                  <td className="px-4 py-3 text-right">
                    <button onClick={() => remove(f.id)} title="Remove"
                      className="p-1.5 rounded-lg hover:bg-red-500/10 hover:text-red-500" style={{ color: "var(--text-secondary)" }}>
                      <Trash2 size={15} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
