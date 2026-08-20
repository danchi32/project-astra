"use client";
/**
 * The support chatbot, floating on every portal page.
 *
 * It answers from the documentation — ASTRA's published guides and the organization's own
 * knowledge base — and nothing else, so every reply arrives with the documents behind it.
 * Those are clickable: an ASTRA guide opens in the panel itself rather than navigating
 * away, because the person reading it is usually mid-task on the page underneath.
 *
 * Deliberately not the same thing as the AI that fixes devices. This one cannot act. When
 * someone needs a machine touched, it says so and points at the tray assistant or at
 * Help & support — a widget that implied it had queued a fix would be worse than useless.
 *
 * Nothing is stored server-side. The transcript lives here, in component state, and is
 * replayed on each question; closing the panel keeps it for the session, and a reload
 * starts fresh.
 */
import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  ArrowLeft, BookOpen, ExternalLink, Loader2, MessageSquare, Send, Sparkles, X,
} from "lucide-react";
import Link from "next/link";
import { askAssistant, getHelpArticle } from "@/lib/api/support";
import type { AssistantSource } from "@/lib/api/types";
import { apiErrorMessage } from "@/lib/utils";

type Turn = {
  role: "user" | "assistant";
  content: string;
  sources?: AssistantSource[];
  /** Set on an assistant turn the documentation could not cover — the turn that offers
   *  a human instead. */
  unresolved?: boolean;
};

const GREETING: Turn = {
  role: "assistant",
  content:
    "Hi — I'm the ASTRA help assistant. Ask me anything about installing the agent, " +
    "devices, self-healing, billing or the portal, and I'll answer from the guides and " +
    "your organization's knowledge base.",
};

const SUGGESTIONS = [
  "How do I install the agent?",
  "Why is a device showing offline?",
  "How do approvals work?",
];

export function SupportChat() {
  const [open, setOpen] = useState(false);
  const [turns, setTurns] = useState<Turn[]>([GREETING]);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [articleId, setArticleId] = useState<string | null>(null);

  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const ask = useMutation({
    mutationFn: askAssistant,
    onSuccess: (reply) =>
      setTurns((prior) => [
        ...prior,
        {
          role: "assistant",
          content: reply.answer,
          sources: reply.sources,
          unresolved: !reply.grounded,
        },
      ]),
    onError: (err) =>
      setError(apiErrorMessage(err, "I couldn't reach the assistant. Please try again.")),
  });

  // Follow the conversation down as it grows, and while the reply is being written.
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns, ask.isPending, open]);

  useEffect(() => {
    if (open && !articleId) inputRef.current?.focus();
  }, [open, articleId]);

  // Escape backs out one level at a time — out of an article, then out of the panel —
  // so it never discards the conversation by surprise.
  useEffect(() => {
    if (!open) return;
    function onKey(event: KeyboardEvent) {
      if (event.key !== "Escape") return;
      setArticleId((current) => {
        if (current) return null;
        setOpen(false);
        return null;
      });
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  function send(question: string) {
    const message = question.trim();
    if (!message || ask.isPending) return;

    setError(null);
    setDraft("");
    // The history sent is what came BEFORE this question — the server appends it itself.
    const history = [...turns, { role: "user" as const, content: message }]
      .filter((t) => t !== GREETING)
      .map(({ role, content }) => ({ role, content }));
    setTurns((prior) => [...prior, { role: "user", content: message }]);
    ask.mutate({ message, history: history.slice(0, -1) });
  }

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        aria-label="Ask the ASTRA help assistant"
        title="Ask the ASTRA help assistant"
        className="fixed bottom-5 right-5 z-40 flex items-center gap-2 pl-3.5 pr-4 py-3 rounded-full text-sm font-medium text-white shadow-lg transition-transform hover:scale-105"
        style={{ background: "var(--accent)" }}
      >
        <MessageSquare size={17} />
        Ask ASTRA
      </button>
    );
  }

  return (
    <div
      role="dialog"
      aria-label="ASTRA help assistant"
      className="fixed bottom-5 right-5 z-40 flex flex-col rounded-2xl overflow-hidden shadow-2xl w-[min(24rem,calc(100vw-2.5rem))] h-[min(34rem,calc(100vh-6rem))]"
      style={{ background: "var(--surface)", border: "1px solid var(--border)" }}
    >
      <header
        className="flex items-center gap-2 px-4 py-3 shrink-0"
        style={{ borderBottom: "1px solid var(--border)" }}
      >
        <div
          className="p-1.5 rounded-lg"
          style={{
            background: "color-mix(in srgb, var(--accent) 12%, transparent)",
            color: "var(--accent)",
          }}
        >
          <Sparkles size={15} />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold truncate" style={{ color: "var(--text-primary)" }}>
            ASTRA help assistant
          </p>
          <p className="text-[11px]" style={{ color: "var(--text-secondary)" }}>
            Answers from the guides and your knowledge base
          </p>
        </div>
        <button onClick={() => setOpen(false)} aria-label="Close" title="Close">
          <X size={17} style={{ color: "var(--text-secondary)" }} />
        </button>
      </header>

      {articleId ? (
        <ArticleReader id={articleId} onBack={() => setArticleId(null)} />
      ) : (
        <>
          <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
            {turns.map((turn, index) => (
              <Bubble key={index} turn={turn} onOpenArticle={setArticleId} />
            ))}

            {turns.length === 1 && (
              <div className="flex flex-wrap gap-1.5 pt-1">
                {SUGGESTIONS.map((suggestion) => (
                  <button
                    key={suggestion}
                    onClick={() => send(suggestion)}
                    className="px-2.5 py-1.5 rounded-lg text-xs text-left"
                    style={{
                      border: "1px solid var(--border)",
                      color: "var(--text-secondary)",
                    }}
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            )}

            {ask.isPending && (
              <div
                className="inline-flex items-center gap-2 text-xs"
                style={{ color: "var(--text-secondary)" }}
              >
                <Loader2 size={13} className="animate-spin" /> Reading the guides…
              </div>
            )}
            {error && (
              <p className="text-xs" style={{ color: "#ef4444" }}>
                {error}
              </p>
            )}
            <div ref={endRef} />
          </div>

          <form
            onSubmit={(event) => {
              event.preventDefault();
              send(draft);
            }}
            className="flex items-center gap-2 px-3 py-3 shrink-0"
            style={{ borderTop: "1px solid var(--border)" }}
          >
            <input
              ref={inputRef}
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              maxLength={1000}
              placeholder="Ask a question…"
              className="flex-1 px-3 py-2 rounded-lg text-sm outline-none"
              style={{
                background: "var(--bg)",
                border: "1px solid var(--border)",
                color: "var(--text-primary)",
              }}
            />
            <button
              type="submit"
              disabled={!draft.trim() || ask.isPending}
              aria-label="Send"
              className="p-2 rounded-lg text-white disabled:opacity-40"
              style={{ background: "var(--accent)" }}
            >
              <Send size={15} />
            </button>
          </form>
        </>
      )}
    </div>
  );
}

function Bubble({
  turn,
  onOpenArticle,
}: {
  turn: Turn;
  onOpenArticle: (id: string) => void;
}) {
  const mine = turn.role === "user";
  return (
    <div className={mine ? "flex justify-end" : "flex justify-start"}>
      <div className="max-w-[85%] space-y-2">
        <div
          className="px-3 py-2 rounded-xl text-sm whitespace-pre-wrap leading-relaxed"
          style={
            mine
              ? { background: "var(--accent)", color: "white" }
              : {
                  background: "var(--bg)",
                  border: "1px solid var(--border)",
                  color: "var(--text-primary)",
                }
          }
        >
          {turn.content}
        </div>

        {!!turn.sources?.length && (
          <div className="space-y-1">
            <p className="text-[10px] uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>
              Based on
            </p>
            {turn.sources.map((source, index) =>
              source.article_id ? (
                <button
                  key={index}
                  onClick={() => onOpenArticle(source.article_id as string)}
                  className="flex items-center gap-1.5 w-full text-left text-xs px-2 py-1.5 rounded-lg"
                  style={{ border: "1px solid var(--border)", color: "var(--accent)" }}
                >
                  <BookOpen size={12} className="shrink-0" />
                  <span className="truncate">{source.title}</span>
                </button>
              ) : (
                // A runbook or FAQ entry has no page to open, so it is named, not linked —
                // a chip that looks clickable and is not is worse than a plain label.
                <p
                  key={index}
                  className="flex items-center gap-1.5 text-xs px-2 py-1.5 rounded-lg"
                  style={{ border: "1px solid var(--border)", color: "var(--text-secondary)" }}
                >
                  <BookOpen size={12} className="shrink-0" />
                  <span className="truncate">{source.title}</span>
                </p>
              )
            )}
          </div>
        )}

        {turn.unresolved && (
          <Link
            href="/help"
            className="inline-flex items-center gap-1.5 text-xs font-medium"
            style={{ color: "var(--accent)" }}
          >
            Raise a support request <ExternalLink size={12} />
          </Link>
        )}
      </div>
    </div>
  );
}

/** One guide, read inside the panel. Navigating to /help would lose the page the person
 *  is standing on, which is usually the page their question is about. */
function ArticleReader({ id, onBack }: { id: string; onBack: () => void }) {
  const { data: article, isLoading, isError } = useQuery({
    queryKey: ["help-article", id],
    queryFn: () => getHelpArticle(id),
  });

  return (
    <div className="flex-1 overflow-y-auto px-4 py-3">
      <button
        onClick={onBack}
        className="inline-flex items-center gap-1.5 text-xs mb-3"
        style={{ color: "var(--accent)" }}
      >
        <ArrowLeft size={13} /> Back to the chat
      </button>

      {isLoading && (
        <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
          Opening the guide…
        </p>
      )}
      {isError && (
        <p className="text-xs" style={{ color: "#ef4444" }}>
          That guide could not be opened. It may have been withdrawn.
        </p>
      )}
      {article && (
        <>
          {article.error_code && (
            <span
              className="inline-block text-[11px] font-mono px-2 py-0.5 rounded mb-1.5"
              style={{
                background: "var(--bg)",
                border: "1px solid var(--border)",
                color: "var(--text-secondary)",
              }}
            >
              {article.error_code}
            </span>
          )}
          <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
            {article.title}
          </h3>
          <p
            className="text-sm mt-2 whitespace-pre-wrap leading-relaxed"
            style={{ color: "var(--text-primary)" }}
          >
            {article.content}
          </p>
        </>
      )}
    </div>
  );
}
