"use client";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { BookOpen, Plus, Trash2, Sparkles } from "lucide-react";
import { listArticles, createArticle, deleteArticle } from "@/lib/api/knowledge";

export default function KnowledgePage() {
  const queryClient = useQueryClient();
  const [adding, setAdding] = useState(false);
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [saving, setSaving] = useState(false);

  const { data: articles, isLoading } = useQuery({
    queryKey: ["knowledge"],
    queryFn: listArticles,
  });

  async function save(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim() || !content.trim()) return;
    setSaving(true);
    try {
      await createArticle(title.trim(), content.trim());
      setTitle("");
      setContent("");
      setAdding(false);
      await queryClient.invalidateQueries({ queryKey: ["knowledge"] });
    } finally {
      setSaving(false);
    }
  }

  async function remove(id: string) {
    await deleteArticle(id);
    await queryClient.invalidateQueries({ queryKey: ["knowledge"] });
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="p-2 rounded-lg" style={{ background: "rgba(37,99,235,0.1)", color: "var(--accent)" }}>
            <BookOpen size={18} />
          </div>
          <div>
            <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>Knowledge Base</h1>
            <p className="text-sm mt-0.5" style={{ color: "var(--text-secondary)" }}>
              Runbooks and how-to guides ASTRA searches to answer questions
            </p>
          </div>
        </div>
        <button onClick={() => setAdding((a) => !a)}
          className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium text-white"
          style={{ background: "var(--accent)" }}>
          <Plus size={16} /> Add article
        </button>
      </div>

      {/* AI note */}
      <div className="flex items-start gap-2 rounded-lg p-3 text-sm"
        style={{ background: "rgba(37,99,235,0.06)", border: "1px solid var(--border)", color: "var(--text-secondary)" }}>
        <Sparkles size={16} style={{ color: "var(--accent)", marginTop: 1 }} />
        <span>When a user asks a how-to question, ASTRA searches these articles and grounds its answer in the most relevant one — so your team&apos;s knowledge is reused automatically.</span>
      </div>

      {adding && (
        <form onSubmit={save} className="rounded-xl p-4 space-y-3"
          style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
          <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Title (e.g. How to connect to the VPN)"
            className="w-full px-3 py-2 rounded-lg text-sm outline-none focus:ring-2 focus:ring-blue-500"
            style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }} />
          <textarea value={content} onChange={(e) => setContent(e.target.value)} rows={5} placeholder="Steps or guidance…"
            className="w-full px-3 py-2 rounded-lg text-sm outline-none focus:ring-2 focus:ring-blue-500 resize-y"
            style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }} />
          <div className="flex gap-2 justify-end">
            <button type="button" onClick={() => setAdding(false)}
              className="px-3 py-2 rounded-lg text-sm font-medium"
              style={{ background: "var(--bg)", color: "var(--text-secondary)", border: "1px solid var(--border)" }}>Cancel</button>
            <button type="submit" disabled={saving || !title.trim() || !content.trim()}
              className="px-3 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50"
              style={{ background: "var(--accent)" }}>{saving ? "Saving…" : "Save article"}</button>
          </div>
        </form>
      )}

      <div className="space-y-3">
        {isLoading && <p className="text-sm" style={{ color: "var(--text-secondary)" }}>Loading…</p>}
        {!isLoading && (!articles || articles.length === 0) && (
          <div className="rounded-xl p-8 text-center" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
            <BookOpen size={36} style={{ color: "var(--accent)", opacity: 0.4, margin: "0 auto" }} />
            <p className="mt-3 text-sm" style={{ color: "var(--text-secondary)" }}>
              No articles yet. Add your first runbook so ASTRA can start using it.
            </p>
          </div>
        )}
        {articles?.map((a) => (
          <div key={a.id} className="rounded-xl p-4 group"
            style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <h3 className="font-medium" style={{ color: "var(--text-primary)" }}>{a.title}</h3>
                <p className="mt-1 text-sm whitespace-pre-wrap" style={{ color: "var(--text-secondary)" }}>{a.content}</p>
                {a.source === "resolved_issue" && (
                  <span className="inline-block mt-2 text-xs px-2 py-0.5 rounded-full"
                    style={{ background: "rgba(16,185,129,0.1)", color: "#10b981" }}>learned from a resolved issue</span>
                )}
              </div>
              <button onClick={() => remove(a.id)} title="Delete"
                className="p-1.5 rounded-lg opacity-0 group-hover:opacity-100 transition-opacity hover:bg-red-500/10 hover:text-red-500"
                style={{ color: "var(--text-secondary)" }}>
                <Trash2 size={15} />
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
