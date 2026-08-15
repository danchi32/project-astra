"use client";
/**
 * Global knowledge — which is also ASTRA's customer-facing help centre.
 *
 * One article, two jobs. The assistant retrieves it when someone describes the problem in
 * their own words, and a human finds it in the help centre when all they have is an error
 * code. Filing it under a category and a code is what turns the first into the second;
 * without them the article still works, it is just harder to stumble on.
 *
 * Withdrawing does both at once, deliberately: an article that stops being shown to
 * customers but keeps being quoted by the assistant is the worst of both.
 */
import { useState } from "react";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, BookOpen, Eye, EyeOff, Plus, Trash2 } from "lucide-react";
import { getMe } from "@/lib/api/auth";
import {
  createGlobalKnowledge, deleteGlobalKnowledge, listGlobalKnowledge, updateGlobalKnowledge,
} from "@/lib/api/platform";
import { getHelpCategoryOptions } from "@/lib/api/support";
import { apiErrorMessage } from "@/lib/utils";

export default function GlobalKnowledgePage() {
  const queryClient = useQueryClient();
  const { data: me } = useQuery({ queryKey: ["me"], queryFn: getMe });
  const enabled = !!me?.is_platform_admin;
  const { data: articles, isLoading } = useQuery({
    queryKey: ["global-knowledge"], queryFn: listGlobalKnowledge, enabled,
  });
  const { data: categories } = useQuery({
    queryKey: ["help-category-options"], queryFn: getHelpCategoryOptions, enabled,
  });

  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [category, setCategory] = useState("");
  const [errorCode, setErrorCode] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function refresh() {
    await queryClient.invalidateQueries({ queryKey: ["global-knowledge"] });
    // The customer-facing lists are built from the same rows.
    await queryClient.invalidateQueries({ queryKey: ["help-articles"] });
    await queryClient.invalidateQueries({ queryKey: ["help-categories"] });
  }

  async function add(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true); setError("");
    try {
      await createGlobalKnowledge({
        title: title.trim(), content: content.trim(),
        help_category: category || null,
        error_code: errorCode.trim() || null,
      });
      setTitle(""); setContent(""); setCategory(""); setErrorCode("");
      await refresh();
    } catch (err) {
      setError(apiErrorMessage(err, "Couldn't save. A title and a solution are required."));
    } finally { setSaving(false); }
  }

  async function togglePublished(id: string, published: boolean) {
    if (published && !confirm(
      "Withdraw this article? Customers stop seeing it in the help centre and the "
      + "assistant stops answering from it."
    )) return;
    await updateGlobalKnowledge(id, { published: !published });
    await refresh();
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
          <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>Support articles</h1>
          <p className="text-sm mt-0.5" style={{ color: "var(--text-secondary)" }}>
            Read by <span className="font-medium">every</span> organization in the help centre, and used by the AI assistant
          </p>
        </div>
      </div>

      <form onSubmit={add} className="rounded-xl p-4 space-y-3" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
        <div>
          <label className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>Problem</label>
          <input required value={title} onChange={(e) => setTitle(e.target.value)}
            placeholder="e.g. Agent install fails: .NET 8 runtime missing"
            className="w-full mt-1 px-3 py-2 rounded-lg text-sm outline-none focus:ring-2 focus:ring-brand-500" style={inputStyle} />
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <label className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>Category</label>
            <select value={category} onChange={(e) => setCategory(e.target.value)}
              className="w-full mt-1 px-3 py-2 rounded-lg text-sm outline-none capitalize" style={inputStyle}>
              <option value="">Not filed (assistant only)</option>
              {categories?.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <div>
            <label className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>
              Error code <span className="font-normal">— what they see on screen</span>
            </label>
            <input value={errorCode} onChange={(e) => setErrorCode(e.target.value)}
              placeholder="0x80070005 or ASTRA-1002" maxLength={40}
              className="w-full mt-1 px-3 py-2 rounded-lg text-sm font-mono outline-none focus:ring-2 focus:ring-brand-500" style={inputStyle} />
          </div>
        </div>

        <div>
          <label className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>Solution</label>
          <textarea required value={content} onChange={(e) => setContent(e.target.value)} rows={5}
            placeholder="Steps that fix it…"
            className="w-full mt-1 px-3 py-2 rounded-lg text-sm outline-none focus:ring-2 focus:ring-brand-500" style={inputStyle} />
        </div>
        {error && <p className="text-sm" style={{ color: "var(--health-bad)" }}>{error}</p>}
        <button type="submit" disabled={saving}
          className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50"
          style={{ background: "var(--accent)" }}>
          <Plus size={15} /> {saving ? "Saving…" : "Publish to all organizations"}
        </button>
      </form>

      <div className="rounded-xl overflow-hidden" style={{ border: "1px solid var(--border)", background: "var(--surface)" }}>
        {isLoading && <p className="px-5 py-8 text-center text-sm" style={{ color: "var(--text-secondary)" }}>Loading…</p>}
        {!isLoading && !articles?.length && (
          <p className="px-5 py-10 text-center text-sm" style={{ color: "var(--text-secondary)" }}>
            No articles yet. Add one above and every organization can read it.
          </p>
        )}
        <ul>
          {articles?.map((a) => {
            const published = a.published_at !== null;
            return (
              <li key={a.id} className="px-5 py-4 flex items-start justify-between gap-4" style={{ borderBottom: "1px solid var(--border)" }}>
                <div className="min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <p className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>{a.title}</p>
                    {a.error_code && (
                      <span className="text-xs font-mono px-1.5 py-0.5 rounded"
                        style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-secondary)" }}>
                        {a.error_code}
                      </span>
                    )}
                    {a.help_category ? (
                      <span className="text-xs capitalize" style={{ color: "var(--text-secondary)" }}>
                        {a.help_category}
                      </span>
                    ) : (
                      <span className="text-xs" style={{ color: "var(--text-secondary)" }} title="Retrievable by the assistant, but not browsable in the help centre">
                        Unfiled
                      </span>
                    )}
                    {!published && (
                      <span className="text-xs px-1.5 py-0.5 rounded-full"
                        style={{ color: "var(--health-warn)", background: "color-mix(in srgb, var(--health-warn) 12%, transparent)" }}>
                        Withdrawn
                      </span>
                    )}
                  </div>
                  <p className="text-sm mt-1 whitespace-pre-wrap" style={{ color: "var(--text-secondary)" }}>{a.content}</p>
                </div>
                <div className="flex items-center gap-1 shrink-0">
                  <button onClick={() => togglePublished(a.id, published)}
                    title={published ? "Withdraw from the help centre and the assistant" : "Publish"}
                    className="p-1.5 rounded-lg hover:bg-brand-500/10" style={{ color: "var(--text-secondary)" }}>
                    {published ? <Eye size={15} /> : <EyeOff size={15} />}
                  </button>
                  <button onClick={() => remove(a.id)} title="Remove"
                    className="p-1.5 rounded-lg hover:bg-red-500/10 hover:text-red-500" style={{ color: "var(--text-secondary)" }}>
                    <Trash2 size={15} />
                  </button>
                </div>
              </li>
            );
          })}
        </ul>
      </div>
    </div>
  );
}
