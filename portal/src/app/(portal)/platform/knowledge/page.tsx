"use client";
import { useState } from "react";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, BookOpen, Plus, Trash2 } from "lucide-react";
import { getMe } from "@/lib/api/auth";
import { listGlobalKnowledge, createGlobalKnowledge, deleteGlobalKnowledge } from "@/lib/api/platform";

export default function GlobalKnowledgePage() {
  const queryClient = useQueryClient();
  const { data: me } = useQuery({ queryKey: ["me"], queryFn: getMe });
  const enabled = !!me?.is_platform_admin;
  const { data: articles, isLoading } = useQuery({
    queryKey: ["global-knowledge"], queryFn: listGlobalKnowledge, enabled,
  });

  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function refresh() {
    await queryClient.invalidateQueries({ queryKey: ["global-knowledge"] });
  }
  async function add(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true); setError("");
    try {
      await createGlobalKnowledge({ title: title.trim(), content: content.trim() });
      setTitle(""); setContent("");
      await refresh();
    } catch {
      setError("Couldn't save. A title and a solution are required.");
    } finally { setSaving(false); }
  }
  async function remove(id: string) {
    if (!confirm("Remove this global article for all organizations?")) return;
    await deleteGlobalKnowledge(id);
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
          <BookOpen size={18} />
        </div>
        <div>
          <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>Global knowledge</h1>
          <p className="text-sm mt-0.5" style={{ color: "var(--text-secondary)" }}>
            Problem → solution articles the AI assistant uses for <span className="font-medium">every</span> organization
          </p>
        </div>
      </div>

      <form onSubmit={add} className="rounded-xl p-4 space-y-3" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
        <div>
          <label className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>Problem</label>
          <input required value={title} onChange={(e) => setTitle(e.target.value)}
            placeholder="e.g. Teams keeps asking to sign in"
            className="w-full mt-1 px-3 py-2 rounded-lg text-sm outline-none focus:ring-2 focus:ring-brand-500" style={inputStyle} />
        </div>
        <div>
          <label className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>Solution</label>
          <textarea required value={content} onChange={(e) => setContent(e.target.value)} rows={4}
            placeholder="Steps that fix it…"
            className="w-full mt-1 px-3 py-2 rounded-lg text-sm outline-none focus:ring-2 focus:ring-brand-500" style={inputStyle} />
        </div>
        {error && <p className="text-sm text-red-500">{error}</p>}
        <button type="submit" disabled={saving}
          className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50"
          style={{ background: "var(--accent)" }}>
          <Plus size={15} /> {saving ? "Saving…" : "Add to all organizations"}
        </button>
      </form>

      <div className="rounded-xl overflow-hidden" style={{ border: "1px solid var(--border)", background: "var(--surface)" }}>
        {isLoading && <p className="px-5 py-8 text-center text-sm" style={{ color: "var(--text-secondary)" }}>Loading…</p>}
        {!isLoading && !articles?.length && (
          <p className="px-5 py-10 text-center text-sm" style={{ color: "var(--text-secondary)" }}>
            No global articles yet. Add one above and every organization&apos;s assistant can use it.
          </p>
        )}
        <ul>
          {articles?.map((a) => (
            <li key={a.id} className="px-5 py-4 flex items-start justify-between gap-4" style={{ borderBottom: "1px solid var(--border)" }}>
              <div className="min-w-0">
                <p className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>{a.title}</p>
                <p className="text-sm mt-1 whitespace-pre-wrap" style={{ color: "var(--text-secondary)" }}>{a.content}</p>
              </div>
              <button onClick={() => remove(a.id)} title="Remove"
                className="p-1.5 rounded-lg hover:bg-red-500/10 hover:text-red-500 shrink-0" style={{ color: "var(--text-secondary)" }}>
                <Trash2 size={15} />
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
