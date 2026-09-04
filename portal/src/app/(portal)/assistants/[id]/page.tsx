"use client";
import { useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronLeft, Bot, Lock, Check, Plus, Wrench } from "lucide-react";
import {
  getAssistant,
  listAssistantTools,
  createVersion,
  publishVersion,
} from "@/lib/api/assistants";
import { getMe } from "@/lib/api/auth";
import type { AssistantVersion } from "@/lib/api/types";

function StatusPill({ v, live }: { v: AssistantVersion; live: boolean }) {
  const style = live
    ? { bg: "rgba(16,185,129,0.1)", fg: "#10b981", text: "Live" }
    : v.status === "draft"
      ? { bg: "rgba(245,158,11,0.12)", fg: "#f59e0b", text: "Draft" }
      : { bg: "rgba(100,116,139,0.12)", fg: "var(--text-secondary)", text: v.status };
  return (
    <span
      className="text-xs px-2 py-0.5 rounded-full"
      style={{ background: style.bg, color: style.fg }}
    >
      {style.text}
    </span>
  );
}

export default function AssistantDetailPage() {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();

  const [drafting, setDrafting] = useState(false);
  const [prompt, setPrompt] = useState("");
  const [notes, setNotes] = useState("");
  const [steps, setSteps] = useState("");
  const [restrict, setRestrict] = useState(false);
  const [granted, setGranted] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { data: me } = useQuery({ queryKey: ["me"], queryFn: getMe });
  const isStaff = me?.role === "admin" || me?.role === "technician";
  const isAdmin = me?.role === "admin";

  const { data: a, isLoading } = useQuery({
    queryKey: ["assistant", id],
    queryFn: () => getAssistant(id),
  });
  const { data: tools } = useQuery({
    queryKey: ["assistant-tools"],
    queryFn: listAssistantTools,
  });

  const editable = Boolean(a && !a.builtin && isStaff);

  async function saveDraft(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await createVersion(id, {
        system_prompt: prompt.trim() || null,
        max_tool_iterations: steps ? Number(steps) : null,
        // undefined would omit the field; null is the explicit "every tool".
        tool_ids: restrict ? granted : null,
        notes: notes.trim() || null,
      });
      setPrompt("");
      setNotes("");
      setSteps("");
      setRestrict(false);
      setGranted([]);
      setDrafting(false);
      await queryClient.invalidateQueries({ queryKey: ["assistant", id] });
    } catch (err: unknown) {
      // The server refuses a step cap above its own limit and an unwired model override.
      // Surfacing its sentence beats a generic failure: it names the limit.
      const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data
        ?.detail;
      setError(
        Array.isArray(detail)
          ? String((detail[0] as { msg?: string })?.msg ?? "Could not save the draft.")
          : String(detail ?? "Could not save the draft."),
      );
    } finally {
      setSaving(false);
    }
  }

  async function publish(versionId: string, versionNo: number) {
    const older = a?.published_version_id && a.published_version_id !== versionId;
    if (
      !confirm(
        older
          ? `Roll back to v${versionNo}?\n\nIt becomes the live version immediately.`
          : `Publish v${versionNo}?\n\nIt starts answering immediately.`,
      )
    )
      return;
    setError(null);
    try {
      await publishVersion(id, versionId);
      await queryClient.invalidateQueries({ queryKey: ["assistant", id] });
      await queryClient.invalidateQueries({ queryKey: ["assistants"] });
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data
        ?.detail;
      setError(detail ?? "Could not publish.");
    }
  }

  if (isLoading) return <p className="text-sm" style={{ color: "var(--text-secondary)" }}>Loading…</p>;
  if (!a) return <p className="text-sm" style={{ color: "var(--text-secondary)" }}>Not found.</p>;

  return (
    <div className="space-y-6">
      <Link
        href="/assistants"
        className="inline-flex items-center gap-1 text-sm"
        style={{ color: "var(--text-secondary)" }}
      >
        <ChevronLeft size={15} /> Assistants
      </Link>

      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <div
            className="p-2 rounded-lg"
            style={{ background: "rgba(154,47,187,0.1)", color: "var(--accent)" }}
          >
            <Bot size={18} />
          </div>
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>
                {a.name}
              </h1>
              {a.builtin && (
                <span
                  className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full"
                  style={{ background: "rgba(100,116,139,0.12)", color: "var(--text-secondary)" }}
                >
                  <Lock size={10} /> Built-in
                </span>
              )}
            </div>
            {a.description && (
              <p className="text-sm mt-0.5" style={{ color: "var(--text-secondary)" }}>
                {a.description}
              </p>
            )}
          </div>
        </div>
        {editable && (
          <button
            onClick={() => setDrafting((d) => !d)}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium text-white shrink-0"
            style={{ background: "var(--accent)" }}
          >
            <Plus size={16} /> New draft
          </button>
        )}
      </div>

      {a.builtin && (
        <div
          className="rounded-lg p-3 text-sm"
          style={{
            background: "rgba(100,116,139,0.08)",
            border: "1px solid var(--border)",
            color: "var(--text-secondary)",
          }}
        >
          ASTRA maintains this one. You can read how it is configured, but not change it —
          create your own assistant to run something different.
        </div>
      )}

      {error && (
        <div
          className="rounded-lg p-3 text-sm"
          style={{ background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.3)", color: "#ef4444" }}
        >
          {error}
        </div>
      )}

      {drafting && editable && (
        <form
          onSubmit={saveDraft}
          className="rounded-xl p-4 space-y-4"
          style={{ background: "var(--surface)", border: "1px solid var(--border)" }}
        >
          <div>
            <label className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>
              Brief
            </label>
            <p className="text-xs mt-0.5 mb-2" style={{ color: "var(--text-secondary)" }}>
              How this assistant should behave. Leave blank to use ASTRA&apos;s standard brief.
            </p>
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              rows={7}
              placeholder="You are our onboarding helper. Answer questions about setting up a new laptop…"
              className="w-full px-3 py-2 rounded-lg text-sm outline-none focus:ring-2 focus:ring-brand-500 resize-y"
              style={{
                background: "var(--bg)",
                border: "1px solid var(--border)",
                color: "var(--text-primary)",
              }}
            />
          </div>

          <div>
            <label className="flex items-center gap-2 text-sm font-medium" style={{ color: "var(--text-primary)" }}>
              <input
                type="checkbox"
                checked={restrict}
                onChange={(e) => setRestrict(e.target.checked)}
              />
              Limit which tools it can use
            </label>
            <p className="text-xs mt-0.5" style={{ color: "var(--text-secondary)" }}>
              Off means every tool ASTRA offers. Ticking it and choosing nothing makes an
              answer-only assistant that takes no action at all.
            </p>
            {restrict && (
              <div className="mt-2 space-y-1.5">
                {tools?.map((t) => (
                  <label
                    key={t.name}
                    className="flex items-start gap-2 text-sm rounded-lg p-2"
                    style={{ background: "var(--bg)", border: "1px solid var(--border)" }}
                  >
                    <input
                      type="checkbox"
                      className="mt-1"
                      checked={granted.includes(t.name)}
                      onChange={(e) =>
                        setGranted((g) =>
                          e.target.checked ? [...g, t.name] : g.filter((n) => n !== t.name),
                        )
                      }
                    />
                    <span className="min-w-0">
                      <span className="font-mono text-xs" style={{ color: "var(--text-primary)" }}>
                        {t.name}
                      </span>
                      <span className="block text-xs mt-0.5" style={{ color: "var(--text-secondary)" }}>
                        {t.description}
                      </span>
                    </span>
                  </label>
                ))}
              </div>
            )}
          </div>

          <div>
            <label className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>
              Investigation steps (optional)
            </label>
            <p className="text-xs mt-0.5 mb-2" style={{ color: "var(--text-secondary)" }}>
              How many tool calls it may make in one turn. Each one is a billed model call,
              so this can go below the platform limit but never above it.
            </p>
            <input
              type="number"
              min={1}
              value={steps}
              onChange={(e) => setSteps(e.target.value)}
              placeholder="Platform default"
              className="w-40 px-3 py-2 rounded-lg text-sm outline-none focus:ring-2 focus:ring-brand-500"
              style={{
                background: "var(--bg)",
                border: "1px solid var(--border)",
                color: "var(--text-primary)",
              }}
            />
          </div>

          <input
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Note for the version list (optional)"
            className="w-full px-3 py-2 rounded-lg text-sm outline-none focus:ring-2 focus:ring-brand-500"
            style={{
              background: "var(--bg)",
              border: "1px solid var(--border)",
              color: "var(--text-primary)",
            }}
          />

          <div className="flex gap-2 justify-end">
            <button
              type="button"
              onClick={() => setDrafting(false)}
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
              disabled={saving}
              className="px-3 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50"
              style={{ background: "var(--accent)" }}
            >
              {saving ? "Saving…" : "Save draft"}
            </button>
          </div>
        </form>
      )}

      <div>
        <h2 className="text-sm font-medium mb-2" style={{ color: "var(--text-primary)" }}>
          Versions
        </h2>
        <p className="text-xs mb-3" style={{ color: "var(--text-secondary)" }}>
          Drafts are edited freely; publishing is what changes the live assistant. Publishing
          an older version again is how you roll back.
        </p>
        <div className="space-y-2">
          {a.versions.length === 0 && (
            <div
              className="rounded-xl p-6 text-center text-sm"
              style={{
                background: "var(--surface)",
                border: "1px solid var(--border)",
                color: "var(--text-secondary)",
              }}
            >
              No versions yet. Create a draft, then publish it to put this assistant to work.
            </div>
          )}
          {a.versions.map((v) => {
            const live = a.published_version_id === v.id;
            return (
              <div
                key={v.id}
                className="rounded-xl p-4"
                style={{
                  background: "var(--surface)",
                  border: live ? "1px solid #10b981" : "1px solid var(--border)",
                }}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-medium" style={{ color: "var(--text-primary)" }}>
                        v{v.version_no}
                      </span>
                      <StatusPill v={v} live={live} />
                      {v.tool_ids === null ? (
                        <span className="inline-flex items-center gap-1 text-xs" style={{ color: "var(--text-secondary)" }}>
                          <Wrench size={11} /> all tools
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-xs" style={{ color: "var(--text-secondary)" }}>
                          <Wrench size={11} />
                          {v.tool_ids.length === 0
                            ? "no tools — answers only"
                            : `${v.tool_ids.length} tool${v.tool_ids.length === 1 ? "" : "s"}`}
                        </span>
                      )}
                      {v.max_tool_iterations !== null && (
                        <span className="text-xs" style={{ color: "var(--text-secondary)" }}>
                          {v.max_tool_iterations} steps
                        </span>
                      )}
                    </div>
                    {v.notes && (
                      <p className="mt-1 text-sm" style={{ color: "var(--text-secondary)" }}>
                        {v.notes}
                      </p>
                    )}
                    {v.system_prompt && (
                      <p
                        className="mt-2 text-xs whitespace-pre-wrap line-clamp-4"
                        style={{ color: "var(--text-secondary)" }}
                      >
                        {v.system_prompt}
                      </p>
                    )}
                    {!v.system_prompt && (
                      <p className="mt-2 text-xs" style={{ color: "var(--text-secondary)" }}>
                        Uses ASTRA&apos;s standard brief.
                      </p>
                    )}
                  </div>
                  {live ? (
                    <span
                      className="inline-flex items-center gap-1 text-xs shrink-0"
                      style={{ color: "#10b981" }}
                    >
                      <Check size={14} /> Live
                    </span>
                  ) : (
                    editable &&
                    isAdmin &&
                    v.status !== "archived" && (
                      <button
                        onClick={() => publish(v.id, v.version_no)}
                        className="px-3 py-1.5 rounded-lg text-sm font-medium shrink-0"
                        style={{
                          background: "var(--bg)",
                          border: "1px solid var(--border)",
                          color: "var(--text-primary)",
                        }}
                      >
                        {a.published_version_id ? "Roll back to this" : "Publish"}
                      </button>
                    )
                  )}
                </div>
              </div>
            );
          })}
        </div>
        {editable && !isAdmin && (
          <p className="text-xs mt-3" style={{ color: "var(--text-secondary)" }}>
            You can write drafts. Publishing decides which tools a model may reach, so an
            admin has to do it.
          </p>
        )}
      </div>
    </div>
  );
}
