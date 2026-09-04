"use client";
import { useState } from "react";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Bot, Plus, Lock, CircleDot, Trash2 } from "lucide-react";
import { listAssistants, createAssistant, archiveAssistant } from "@/lib/api/assistants";
import { getMe } from "@/lib/api/auth";
import type { Assistant } from "@/lib/api/types";

/** Live or not — and the distinction is the point of the whole feature.
 *
 *  An assistant with no published version exists but answers nobody: its drafts have not
 *  been approved. Showing "Draft only" rather than nothing is what stops someone building
 *  an assistant, walking away, and assuming it is working. */
function StateBadge({ a }: { a: Assistant }) {
  const live = a.published_version_id !== null;
  return (
    <span
      className="inline-flex items-center gap-1.5 text-xs px-2 py-0.5 rounded-full"
      style={{
        background: live ? "rgba(16,185,129,0.1)" : "rgba(100,116,139,0.12)",
        color: live ? "#10b981" : "var(--text-secondary)",
      }}
    >
      <CircleDot size={11} />
      {live ? "Published" : "Draft only — not answering yet"}
    </span>
  );
}

export default function AssistantsPage() {
  const queryClient = useQueryClient();
  const [adding, setAdding] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [saving, setSaving] = useState(false);

  const { data: me } = useQuery({ queryKey: ["me"], queryFn: getMe });
  const isStaff = me?.role === "admin" || me?.role === "technician";

  const { data: assistants, isLoading } = useQuery({
    queryKey: ["assistants"],
    queryFn: listAssistants,
  });

  async function save(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setSaving(true);
    try {
      await createAssistant(name.trim(), description.trim() || undefined);
      setName("");
      setDescription("");
      setAdding(false);
      await queryClient.invalidateQueries({ queryKey: ["assistants"] });
    } finally {
      setSaving(false);
    }
  }

  async function archive(a: Assistant) {
    if (!confirm(`Archive "${a.name}"?\n\nIt stops answering. Past runs keep referring to it.`))
      return;
    await archiveAssistant(a.id);
    await queryClient.invalidateQueries({ queryKey: ["assistants"] });
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div
            className="p-2 rounded-lg"
            style={{ background: "rgba(154,47,187,0.1)", color: "var(--accent)" }}
          >
            <Bot size={18} />
          </div>
          <div>
            <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>
              Assistants
            </h1>
            <p className="text-sm mt-0.5" style={{ color: "var(--text-secondary)" }}>
              The AI personas your team can run, and what each one is allowed to do
            </p>
          </div>
        </div>
        {isStaff && (
          <button
            onClick={() => setAdding((a) => !a)}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium text-white"
            style={{ background: "var(--accent)" }}
          >
            <Plus size={16} /> New assistant
          </button>
        )}
      </div>

      <div
        className="flex items-start gap-2 rounded-lg p-3 text-sm"
        style={{
          background: "rgba(154,47,187,0.06)",
          border: "1px solid var(--border)",
          color: "var(--text-secondary)",
        }}
      >
        <Lock size={16} style={{ color: "var(--accent)", marginTop: 1 }} />
        <span>
          Giving an assistant a tool can only ever <strong>narrow</strong> what it may do. The
          approval tiers still apply on top, so no assistant can reach an admin-only fix
          however it is configured.
        </span>
      </div>

      {adding && (
        <form
          onSubmit={save}
          className="rounded-xl p-4 space-y-3"
          style={{ background: "var(--surface)", border: "1px solid var(--border)" }}
        >
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Name (e.g. Onboarding Helper)"
            className="w-full px-3 py-2 rounded-lg text-sm outline-none focus:ring-2 focus:ring-brand-500"
            style={{
              background: "var(--bg)",
              border: "1px solid var(--border)",
              color: "var(--text-primary)",
            }}
          />
          <input
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="What is it for? (optional)"
            className="w-full px-3 py-2 rounded-lg text-sm outline-none focus:ring-2 focus:ring-brand-500"
            style={{
              background: "var(--bg)",
              border: "1px solid var(--border)",
              color: "var(--text-primary)",
            }}
          />
          <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
            This creates the assistant only. You give it a brief and its tools on the next
            screen, then publish when you are happy with it.
          </p>
          <div className="flex gap-2 justify-end">
            <button
              type="button"
              onClick={() => setAdding(false)}
              className="px-3 py-2 rounded-lg text-sm font-medium"
              style={{
                background: "var(--bg)",
                color: "var(--text-secondary)",
                border: "1px solid var(--border)",
              }}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving || !name.trim()}
              className="px-3 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50"
              style={{ background: "var(--accent)" }}
            >
              {saving ? "Creating…" : "Create assistant"}
            </button>
          </div>
        </form>
      )}

      <div className="space-y-3">
        {isLoading && (
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
            Loading…
          </p>
        )}
        {!isLoading && (!assistants || assistants.length === 0) && (
          <div
            className="rounded-xl p-8 text-center"
            style={{ background: "var(--surface)", border: "1px solid var(--border)" }}
          >
            <Bot size={36} style={{ color: "var(--accent)", opacity: 0.4, margin: "0 auto" }} />
            <p className="mt-3 text-sm" style={{ color: "var(--text-secondary)" }}>
              No assistants yet.
            </p>
          </div>
        )}
        {assistants?.map((a) => (
          <div
            key={a.id}
            className="rounded-xl p-4 group"
            style={{ background: "var(--surface)", border: "1px solid var(--border)" }}
          >
            <div className="flex items-start justify-between gap-3">
              <Link href={`/assistants/${a.id}`} className="min-w-0 flex-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <h3 className="font-medium" style={{ color: "var(--text-primary)" }}>
                    {a.name}
                  </h3>
                  {a.builtin && (
                    <span
                      className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full"
                      style={{ background: "rgba(100,116,139,0.12)", color: "var(--text-secondary)" }}
                      title="Maintained by ASTRA. Readable here, edited only by the platform."
                    >
                      <Lock size={10} /> Built-in
                    </span>
                  )}
                  <StateBadge a={a} />
                </div>
                {a.description && (
                  <p className="mt-1 text-sm" style={{ color: "var(--text-secondary)" }}>
                    {a.description}
                  </p>
                )}
              </Link>
              {isStaff && !a.builtin && (
                <button
                  onClick={() => archive(a)}
                  title="Archive"
                  className="p-1.5 rounded-lg opacity-0 group-hover:opacity-100 transition-opacity hover:bg-red-500/10 hover:text-red-500"
                  style={{ color: "var(--text-secondary)" }}
                >
                  <Trash2 size={15} />
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
