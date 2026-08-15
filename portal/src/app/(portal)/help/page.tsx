"use client";
/**
 * Help and support, from the customer's side.
 *
 * Two tabs rather than two pages, because they are one errand: someone arrives stuck. The
 * articles are tried first — they are instant, and most problems have been seen before —
 * and raising a request is one click away when they are not enough. Putting the search in
 * front of the form is the whole deflection strategy.
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft, BookOpen, LifeBuoy, MessageSquarePlus, Search, Send, Tag,
} from "lucide-react";
import {
  createSupportRequest, getHelpArticle, getHelpCategories, getSupportRequest,
  listSupportRequests, replyToSupportRequest, searchHelpArticles,
} from "@/lib/api/support";
import { getHelpCategoryOptions } from "@/lib/api/support";
import type { SupportRequestPriority } from "@/lib/api/types";
import { apiErrorMessage, formatRelativeTime } from "@/lib/utils";
import {
  DiagnosticsPanel, MessageThread, Panel, PriorityPill, StatusPill,
} from "@/components/support/support-ui";

type Tab = "articles" | "requests";

export default function HelpPage() {
  const [tab, setTab] = useState<Tab>("articles");

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-2.5">
          <div
            className="p-2 rounded-lg shrink-0"
            style={{ background: "color-mix(in srgb, var(--accent) 12%, transparent)", color: "var(--accent)" }}
          >
            <LifeBuoy size={18} />
          </div>
          <div>
            <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>
              Help &amp; support
            </h1>
            <p className="text-sm mt-0.5" style={{ color: "var(--text-secondary)" }}>
              Search the guides, or ask the ASTRA team directly
            </p>
          </div>
        </div>
        <div className="flex items-center gap-1.5">
          {([
            ["articles", "Guides", BookOpen],
            ["requests", "My requests", MessageSquarePlus],
          ] as const).map(([key, label, Icon]) => {
            const active = tab === key;
            return (
              <button
                key={key}
                onClick={() => setTab(key)}
                className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors"
                style={{
                  background: active ? "color-mix(in srgb, var(--accent) 12%, transparent)" : "transparent",
                  color: active ? "var(--accent)" : "var(--text-secondary)",
                  border: `1px solid ${active ? "var(--accent)" : "var(--border)"}`,
                }}
              >
                <Icon size={15} /> {label}
              </button>
            );
          })}
        </div>
      </div>

      {tab === "articles" ? <ArticlesTab onAskInstead={() => setTab("requests")} /> : <RequestsTab />}
    </div>
  );
}

/* ── guides ──────────────────────────────────────────────────────────────── */

function ArticlesTab({ onAskInstead }: { onAskInstead: () => void }) {
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState<string | null>(null);
  const [openId, setOpenId] = useState<string | null>(null);

  const { data: categories } = useQuery({
    queryKey: ["help-categories"],
    queryFn: getHelpCategories,
  });
  const { data: articles, isLoading } = useQuery({
    queryKey: ["help-articles", query, category],
    // An error code pasted into the box is still just text — the server searches the code
    // column too, so one input covers both "0x80070005" and "printer".
    queryFn: () => searchHelpArticles({
      q: query.trim() || undefined,
      category: category ?? undefined,
    }),
  });
  const { data: article } = useQuery({
    queryKey: ["help-article", openId],
    queryFn: () => getHelpArticle(openId as string),
    enabled: !!openId,
  });

  if (openId && article) {
    return (
      <Panel>
        <button
          onClick={() => setOpenId(null)}
          className="inline-flex items-center gap-1.5 text-xs mb-4"
          style={{ color: "var(--accent)" }}
        >
          <ArrowLeft size={13} /> Back to guides
        </button>
        <div className="flex items-center gap-2 flex-wrap mb-1">
          {article.error_code && (
            <span
              className="text-xs font-mono px-2 py-0.5 rounded"
              style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-secondary)" }}
            >
              {article.error_code}
            </span>
          )}
          {article.help_category && (
            <span className="text-xs capitalize" style={{ color: "var(--text-secondary)" }}>
              {article.help_category}
            </span>
          )}
        </div>
        <h2 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>
          {article.title}
        </h2>
        <p
          className="text-sm mt-3 whitespace-pre-wrap leading-relaxed"
          style={{ color: "var(--text-primary)" }}
        >
          {article.content}
        </p>
        <div className="mt-5 pt-4 flex items-center justify-between gap-3 flex-wrap"
          style={{ borderTop: "1px solid var(--border)" }}>
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
            Did this not solve it?
          </p>
          <button
            onClick={onAskInstead}
            className="px-3 py-2 rounded-lg text-sm font-medium text-white"
            style={{ background: "var(--accent)" }}
          >
            Ask the ASTRA team
          </button>
        </div>
      </Panel>
    );
  }

  return (
    <div className="space-y-4">
      <Panel>
        <div className="flex items-center gap-2 px-3 py-2 rounded-lg"
          style={{ background: "var(--bg)", border: "1px solid var(--border)" }}>
          <Search size={15} style={{ color: "var(--text-secondary)" }} />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search guides, or paste an error code"
            className="flex-1 bg-transparent text-sm outline-none"
            style={{ color: "var(--text-primary)" }}
          />
        </div>

        {categories && Object.keys(categories).length > 0 && (
          <div className="flex items-center gap-1.5 flex-wrap mt-3">
            <button
              onClick={() => setCategory(null)}
              className="px-2.5 py-1 rounded-lg text-xs font-medium capitalize"
              style={{
                background: category === null ? "color-mix(in srgb, var(--accent) 12%, transparent)" : "transparent",
                color: category === null ? "var(--accent)" : "var(--text-secondary)",
                border: `1px solid ${category === null ? "var(--accent)" : "var(--border)"}`,
              }}
            >
              All
            </button>
            {Object.entries(categories).map(([name, count]) => {
              const active = category === name;
              return (
                <button
                  key={name}
                  onClick={() => setCategory(active ? null : name)}
                  className="px-2.5 py-1 rounded-lg text-xs font-medium capitalize"
                  style={{
                    background: active ? "color-mix(in srgb, var(--accent) 12%, transparent)" : "transparent",
                    color: active ? "var(--accent)" : "var(--text-secondary)",
                    border: `1px solid ${active ? "var(--accent)" : "var(--border)"}`,
                  }}
                >
                  {name} <span className="tabular-nums opacity-70">{count}</span>
                </button>
              );
            })}
          </div>
        )}
      </Panel>

      {isLoading ? (
        <Panel><div className="h-24 animate-pulse rounded-lg" style={{ background: "var(--bg)" }} /></Panel>
      ) : (articles?.length ?? 0) === 0 ? (
        <Panel>
          <div className="text-center py-8">
            <BookOpen size={22} className="mx-auto" style={{ color: "var(--text-secondary)" }} />
            <p className="text-sm mt-2" style={{ color: "var(--text-primary)" }}>
              {query ? "Nothing matches that yet." : "No guides published yet."}
            </p>
            <p className="text-xs mt-1" style={{ color: "var(--text-secondary)" }}>
              The ASTRA team can help directly.
            </p>
            <button
              onClick={onAskInstead}
              className="mt-4 px-3 py-2 rounded-lg text-sm font-medium text-white"
              style={{ background: "var(--accent)" }}
            >
              Ask the ASTRA team
            </button>
          </div>
        </Panel>
      ) : (
        <div className="rounded-xl overflow-hidden" style={{ border: "1px solid var(--border)" }}>
          <ul style={{ background: "var(--surface)" }}>
            {articles?.map((a) => (
              <li key={a.id} style={{ borderBottom: "1px solid var(--border)" }}>
                <button
                  onClick={() => setOpenId(a.id)}
                  className="w-full text-left px-4 py-3 transition-colors hover:bg-brand-500/5"
                >
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>
                      {a.title}
                    </span>
                    {a.error_code && (
                      <span
                        className="text-xs font-mono px-1.5 py-0.5 rounded"
                        style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-secondary)" }}
                      >
                        {a.error_code}
                      </span>
                    )}
                  </div>
                  {a.help_category && (
                    <span
                      className="inline-flex items-center gap-1 text-xs mt-1 capitalize"
                      style={{ color: "var(--text-secondary)" }}
                    >
                      <Tag size={11} /> {a.help_category}
                    </span>
                  )}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

/* ── my requests ─────────────────────────────────────────────────────────── */

function RequestsTab() {
  const [openId, setOpenId] = useState<string | null>(null);
  const [composing, setComposing] = useState(false);

  const { data: requests, isLoading } = useQuery({
    queryKey: ["support-requests"],
    queryFn: () => listSupportRequests(),
    refetchInterval: 60_000,
  });

  if (composing) {
    return <NewRequestForm onDone={(id) => { setComposing(false); setOpenId(id); }}
      onCancel={() => setComposing(false)} />;
  }
  if (openId) return <RequestThread id={openId} onBack={() => setOpenId(null)} />;

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <button
          onClick={() => setComposing(true)}
          className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium text-white"
          style={{ background: "var(--accent)" }}
        >
          <MessageSquarePlus size={15} /> New request
        </button>
      </div>

      {isLoading ? (
        <Panel><div className="h-24 animate-pulse rounded-lg" style={{ background: "var(--bg)" }} /></Panel>
      ) : (requests?.length ?? 0) === 0 ? (
        <Panel>
          <div className="text-center py-8">
            <LifeBuoy size={22} className="mx-auto" style={{ color: "var(--text-secondary)" }} />
            <p className="text-sm mt-2" style={{ color: "var(--text-primary)" }}>
              You have not asked us anything yet.
            </p>
            <p className="text-xs mt-1" style={{ color: "var(--text-secondary)" }}>
              We attach your fleet&apos;s current state automatically, so you do not have to
              describe your setup.
            </p>
          </div>
        </Panel>
      ) : (
        <div className="rounded-xl overflow-hidden" style={{ border: "1px solid var(--border)" }}>
          <ul style={{ background: "var(--surface)" }}>
            {requests?.map((r) => (
              <li key={r.id} style={{ borderBottom: "1px solid var(--border)" }}>
                <button
                  onClick={() => setOpenId(r.id)}
                  className="w-full text-left px-4 py-3 flex items-center gap-3 transition-colors hover:bg-brand-500/5"
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>
                        {r.subject}
                      </span>
                      <span className="text-xs font-mono" style={{ color: "var(--text-secondary)" }}>
                        {r.reference}
                      </span>
                    </div>
                    <span className="text-xs" style={{ color: "var(--text-secondary)" }}>
                      {r.last_reply_at ? `Last activity ${formatRelativeTime(r.last_reply_at)}` : "Just raised"}
                    </span>
                  </div>
                  <PriorityPill priority={r.priority} />
                  <StatusPill status={r.status} />
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function NewRequestForm({ onDone, onCancel }: { onDone: (id: string) => void; onCancel: () => void }) {
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [category, setCategory] = useState<string>("");
  const [priority, setPriority] = useState<SupportRequestPriority>("normal");
  const [error, setError] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const { data: options } = useQuery({
    queryKey: ["help-category-options"],
    queryFn: getHelpCategoryOptions,
  });

  const mutation = useMutation({
    mutationFn: () => createSupportRequest({
      subject, body, category: category || null, priority,
    }),
    onSuccess: (created) => {
      queryClient.invalidateQueries({ queryKey: ["support-requests"] });
      onDone(created.id);
    },
    onError: (e) => setError(apiErrorMessage(e, "Could not send your request.")),
  });

  const field = {
    background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)",
  } as const;

  return (
    <Panel>
      <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
        Ask the ASTRA team
      </h2>
      <p className="text-xs mt-0.5 mb-4" style={{ color: "var(--text-secondary)" }}>
        Your plan, fleet size and how many devices are reporting in are attached
        automatically — you do not need to describe your setup.
      </p>

      <form
        className="flex flex-col gap-3"
        onSubmit={(e) => { e.preventDefault(); setError(null); mutation.mutate(); }}
      >
        <label className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>
          Subject
          <input
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            required
            maxLength={200}
            placeholder="Agent will not install on Windows 11"
            className="w-full mt-1 px-3 py-2 rounded-lg text-sm outline-none"
            style={field}
          />
        </label>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <label className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>
            Area
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="w-full mt-1 px-3 py-2 rounded-lg text-sm outline-none capitalize"
              style={field}
            >
              <option value="">Not sure</option>
              {options?.map((o) => <option key={o} value={o}>{o}</option>)}
            </select>
          </label>
          <label className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>
            How urgent
            <select
              value={priority}
              onChange={(e) => setPriority(e.target.value as SupportRequestPriority)}
              className="w-full mt-1 px-3 py-2 rounded-lg text-sm outline-none"
              style={field}
            >
              <option value="low">Low — a question</option>
              <option value="normal">Normal — something is awkward</option>
              <option value="high">High — people are blocked</option>
            </select>
          </label>
        </div>

        <label className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>
          What is happening
          <textarea
            value={body}
            onChange={(e) => setBody(e.target.value)}
            required
            rows={7}
            maxLength={10000}
            placeholder="What you tried, what happened, and any error code you saw."
            className="w-full mt-1 px-3 py-2 rounded-lg text-sm outline-none resize-y"
            style={field}
          />
        </label>

        {error && <p className="text-xs" style={{ color: "var(--health-bad)" }}>{error}</p>}

        <div className="flex items-center gap-2">
          <button
            type="submit"
            disabled={mutation.isPending}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-60"
            style={{ background: "var(--accent)" }}
          >
            <Send size={14} /> {mutation.isPending ? "Sending…" : "Send request"}
          </button>
          <button
            type="button"
            onClick={onCancel}
            className="px-3 py-2 rounded-lg text-sm"
            style={{ color: "var(--text-secondary)", border: "1px solid var(--border)" }}
          >
            Cancel
          </button>
        </div>
      </form>
    </Panel>
  );
}

function RequestThread({ id, onBack }: { id: string; onBack: () => void }) {
  const [reply, setReply] = useState("");
  const queryClient = useQueryClient();

  const { data: request } = useQuery({
    queryKey: ["support-request", id],
    queryFn: () => getSupportRequest(id),
    refetchInterval: 30_000,
  });

  const mutation = useMutation({
    mutationFn: () => replyToSupportRequest(id, reply),
    onSuccess: () => {
      setReply("");
      queryClient.invalidateQueries({ queryKey: ["support-request", id] });
      queryClient.invalidateQueries({ queryKey: ["support-requests"] });
    },
  });

  if (!request) {
    return <Panel><div className="h-32 animate-pulse rounded-lg" style={{ background: "var(--bg)" }} /></Panel>;
  }

  return (
    <div className="space-y-4">
      <button
        onClick={onBack}
        className="inline-flex items-center gap-1.5 text-xs"
        style={{ color: "var(--accent)" }}
      >
        <ArrowLeft size={13} /> Back to my requests
      </button>

      <Panel>
        <div className="flex items-start justify-between gap-3 flex-wrap">
          <div>
            <h2 className="text-base font-semibold" style={{ color: "var(--text-primary)" }}>
              {request.subject}
            </h2>
            <p className="text-xs mt-0.5 font-mono" style={{ color: "var(--text-secondary)" }}>
              {request.reference}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <PriorityPill priority={request.priority} />
            <StatusPill status={request.status} />
          </div>
        </div>

        <div className="mt-4">
          <DiagnosticsPanel diagnostics={request.diagnostics} />
        </div>

        <div className="mt-5 pt-4" style={{ borderTop: "1px solid var(--border)" }}>
          <MessageThread messages={request.messages} />
        </div>

        <form
          className="mt-4 pt-4 flex flex-col gap-2"
          style={{ borderTop: "1px solid var(--border)" }}
          onSubmit={(e) => { e.preventDefault(); if (reply.trim()) mutation.mutate(); }}
        >
          <textarea
            value={reply}
            onChange={(e) => setReply(e.target.value)}
            rows={3}
            maxLength={10000}
            placeholder="Add a reply…"
            className="w-full px-3 py-2 rounded-lg text-sm outline-none resize-y"
            style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
          />
          <button
            type="submit"
            disabled={!reply.trim() || mutation.isPending}
            className="self-start inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50"
            style={{ background: "var(--accent)" }}
          >
            <Send size={14} /> {mutation.isPending ? "Sending…" : "Reply"}
          </button>
        </form>
      </Panel>
    </div>
  );
}
