"use client";
import { useState } from "react";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ClipboardList, Download, Trash2, Upload } from "lucide-react";
import {
  deleteAuditPack, editAuditPackRow, exportAuditPack, getAuditPack, getAuditPacks, uploadAuditPack,
  type AuditPack, type AuditPackRow,
} from "@/lib/api/reports";
import { isUpgradeRequired, UpgradeRequired, requiredFeature } from "@/components/upgrade-required";
import { apiErrorMessage } from "@/lib/utils";

// Phase 3b · I4 — Client-Audit Pack. Upload a client's security questionnaire (.xlsx / .csv);
// SAVIO drafts each answer from its own evidence with links to it, and marks what the evidence
// cannot answer as a gap. Drafts: a person reviews them before the CSV goes to the client.

const BADGE: Record<AuditPackRow["status"], { label: string; color: string }> = {
  answered: { label: "Answered", color: "#10b981" }, gap: { label: "Gap", color: "#f59e0b" },
  pending: { label: "Drafting…", color: "var(--text-secondary)" },
};

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(String(r.result).split(",", 2)[1] ?? "");
    r.onerror = () => reject(r.error);
    r.readAsDataURL(file);
  });
}

function Row({ pack, row, onSaved }: { pack: AuditPack; row: AuditPackRow; onSaved: (p: AuditPack) => void }) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(row.answer ?? "");
  const [msg, setMsg] = useState<string | null>(null);
  const muted = { color: "var(--text-secondary)" };
  const input = { background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" };

  async function save(status: "answered" | "gap") {
    setMsg(null);
    try { onSaved(await editAuditPackRow(pack.id, row.n, text.trim(), status)); setEditing(false); }
    catch (e) { setMsg(apiErrorMessage(e, "Could not save.")); }
  }

  const b = BADGE[row.status];
  return (
    <div className="rounded-xl p-4 space-y-2" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
      <div className="flex items-start gap-3 text-sm" style={{ color: "var(--text-primary)" }}>
        <span className="shrink-0 w-8" style={muted}>{row.n}.</span>
        <span className="flex-1 font-medium">{row.question}</span>
        <span className="shrink-0 text-xs px-2 py-0.5 rounded-full" style={{ color: b.color, border: `1px solid ${b.color}` }}>{b.label}</span>
      </div>
      {!editing && row.status !== "pending" && (
        <div className="pl-11 space-y-1">
          <p className="text-sm whitespace-pre-wrap" style={{ color: "var(--text-primary)" }}>{row.answer || <span style={muted}>No answer yet.</span>}</p>
          <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs">
            {row.evidence.map((e) => (
              <Link key={e.key} href={e.link} className="underline" style={{ color: "var(--accent)" }}>{e.label}</Link>
            ))}
            {row.edited_by && <span style={muted}>Reviewed by {row.edited_by}</span>}
            {pack.status === "ready" && (
              <button onClick={() => { setText(row.answer ?? ""); setEditing(true); }} className="underline" style={muted}>Edit</button>
            )}
          </div>
        </div>
      )}
      {editing && (
        <div className="pl-11 space-y-2">
          <textarea aria-label={`Answer to question ${row.n}`} rows={3} maxLength={1500} value={text} onChange={(e) => setText(e.target.value)}
            className="w-full px-3 py-2 rounded-lg text-sm outline-none" style={input} />
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <button onClick={() => save("answered")} disabled={!text.trim()}
              className="px-2.5 py-1 rounded-lg font-medium text-white disabled:opacity-50" style={{ background: "var(--accent)" }}>Save as answered</button>
            <button onClick={() => save("gap")} className="px-2.5 py-1 rounded-lg" style={input}>Save as a gap</button>
            <button onClick={() => setEditing(false)} className="underline" style={muted}>Cancel</button>
            {msg && <span style={{ color: "#ef4444" }}>{msg}</span>}
          </div>
        </div>
      )}
    </div>
  );
}

export default function AuditPackPage() {
  const qc = useQueryClient();
  const [selected, setSelected] = useState<string | null>(null);
  const [gapsOnly, setGapsOnly] = useState(false);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const list = useQuery({ queryKey: ["audit-packs"], queryFn: getAuditPacks, retry: false });
  const current = selected ?? list.data?.[0]?.id ?? null;
  const pack = useQuery({
    queryKey: ["audit-pack", current], queryFn: () => getAuditPack(current!), enabled: !!current,
    // While SAVIO drafts, the answers arrive a batch at a time.
    refetchInterval: (q) => (q.state.data?.status === "answering" ? 3000 : false),
  });
  const muted = { color: "var(--text-secondary)" };
  const panel = { background: "var(--surface)", border: "1px solid var(--border)" };
  const forbidden = (list.error as { response?: { status?: number } } | null)?.response?.status === 403;

  if (isUpgradeRequired(list.error)) return <UpgradeRequired feature={requiredFeature(list.error)} />;
  if (forbidden) return <p className="text-sm" style={muted}>Only an admin can answer client questionnaires.</p>;

  async function upload(file: File) {
    setMsg(null);
    setBusy(true);
    try {
      const p = await uploadAuditPack(file.name, await fileToBase64(file));
      setSelected(p.id);
      await qc.invalidateQueries({ queryKey: ["audit-packs"] });
    } catch (e) { setMsg(apiErrorMessage(e, "Could not upload.")); }
    setBusy(false);
  }

  async function download(p: AuditPack) {
    const res = await exportAuditPack(p.id);
    const name = /filename="([^"]+)"/.exec(String(res.headers["content-disposition"] ?? ""))?.[1] ?? "SAVIO answers.csv";
    const url = URL.createObjectURL(res.data);
    const a = document.createElement("a");
    a.href = url;
    a.download = name;
    a.click();
    URL.revokeObjectURL(url);
  }

  async function remove(p: AuditPack) {
    if (!window.confirm(`Delete "${p.name}" and its answers? This cannot be undone.`)) return;
    await deleteAuditPack(p.id);
    setSelected(null);
    await qc.invalidateQueries({ queryKey: ["audit-packs"] });
  }

  const p = pack.data;
  const rows = p ? (gapsOnly ? p.rows.filter((r) => r.status === "gap") : p.rows) : [];
  const drafted = p ? p.rows.filter((r) => r.status !== "pending").length : 0;

  return (
    <div className="space-y-4 max-w-5xl">
      <Link href="/reports" className="flex items-center gap-1 text-sm" style={muted}><ArrowLeft size={14} /> Reports</Link>
      <div className="flex flex-wrap items-start gap-3">
        <div className="p-2 rounded-lg" style={{ background: "rgba(37,99,235,0.12)", color: "var(--accent)" }}><ClipboardList size={18} /></div>
        <div className="flex-1 min-w-0">
          <h1 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>Client-Audit Pack</h1>
          <p className="text-xs max-w-2xl" style={muted}>
            Upload a client&apos;s security questionnaire (.xlsx or .csv, up to 300 questions). SAVIO drafts each answer from its
            own records, links the evidence, and marks what it cannot show as a gap. Review the drafts before you send them.
          </p>
        </div>
        <label className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium text-white cursor-pointer"
          style={{ background: "var(--accent)", opacity: busy ? 0.6 : 1 }}>
          <Upload size={15} /> {busy ? "Uploading…" : "Upload questionnaire"}
          <input type="file" accept=".xlsx,.csv" className="hidden" disabled={busy}
            onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ""; if (f) void upload(f); }} />
        </label>
      </div>
      {msg && <p className="text-sm" style={{ color: "#ef4444" }}>{msg}</p>}

      {list.data && list.data.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {list.data.map((x) => (
            <button key={x.id} onClick={() => setSelected(x.id)} className="px-3 py-1.5 rounded-lg text-xs text-left"
              style={x.id === current ? { background: "rgba(37,99,235,0.12)", color: "var(--accent)", border: "1px solid var(--accent)" }
                : { ...panel, color: "var(--text-primary)" }}>
              {x.name} <span style={muted}>· {new Date(x.created_at).toLocaleDateString()}</span>
            </button>
          ))}
        </div>
      )}
      {list.data?.length === 0 && <p className="text-sm" style={muted}>No questionnaires yet.</p>}

      {p && (
        <>
          <div className="rounded-xl p-4 flex flex-wrap items-center gap-4" style={panel}>
            <div className="flex-1 text-sm" style={{ color: "var(--text-primary)" }}>
              <div className="font-medium">{p.name}</div>
              {p.status === "answering" && <div style={muted}>SAVIO is drafting answers: {drafted} of {p.questions} so far.</div>}
              {p.status === "failed" && <div style={{ color: "#ef4444" }}>{p.error}</div>}
              {p.status === "ready" && (
                <div style={muted}>{p.answered} answered from SAVIO&apos;s evidence, {p.gaps} gap(s), of {p.questions} questions.</div>
              )}
            </div>
            <label className="flex items-center gap-1.5 text-xs" style={{ color: "var(--text-primary)" }}>
              <input type="checkbox" checked={gapsOnly} onChange={(e) => setGapsOnly(e.target.checked)} /> Gaps only
            </label>
            <button onClick={() => download(p)} disabled={p.status !== "ready"}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm disabled:opacity-50" style={{ ...panel, color: "var(--text-primary)" }}>
              <Download size={14} /> Download CSV
            </button>
            <button onClick={() => remove(p)} title="Delete" className="p-1.5 rounded-lg" style={{ ...panel, color: "var(--text-secondary)" }}>
              <Trash2 size={14} />
            </button>
          </div>
          {rows.map((r) => (
            <Row key={`${p.id}-${r.n}-${r.status}-${r.edited_by ?? ""}`} pack={p} row={r}
              onSaved={(next) => qc.setQueryData(["audit-pack", p.id], next)} />
          ))}
          <p className="text-xs" style={muted}>
            Answers are drafts from SAVIO&apos;s own records. They do not certify anything: check each one before it goes to your client.
          </p>
        </>
      )}
    </div>
  );
}
