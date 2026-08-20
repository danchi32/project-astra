"use client";

import { useEffect, useRef, useState } from "react";
import { Loader2, MessageSquare, Send, Sparkles, X } from "lucide-react";
import Link from "next/link";
import { site } from "@/lib/site";
import { trackEvent } from "@/lib/analytics";

/**
 * The site assistant — a floating bubble on every page that answers visitors' questions
 * about ASTRA and Technomate.
 *
 * It answers from documentation, not from a model's memory: the ASTRA API retrieves the
 * published FAQ and help articles and lets the model write only from those. Which is why
 * this widget has no fallback answer of its own. When the API is unreachable, or has
 * nothing on the subject, the visitor is handed to a person rather than to a guess — a
 * chatbot on a sales site that invents a price does real damage.
 *
 * The site is a static export with no server of its own, so this calls the API directly
 * from the browser. That endpoint is public by design: it reads only published material,
 * writes nothing, and is rate limited per address at the far end.
 */

type Turn = { role: "user" | "assistant"; content: string };

const GREETING: Turn = {
  role: "assistant",
  content:
    "Hi — ask me anything about ASTRA: what it does, how it's priced, how a rollout " +
    "works, or how to reach the team.",
};

const SUGGESTIONS = [
  "What does ASTRA actually do?",
  "How is it priced?",
  "How long does a rollout take?",
];

/** Where the assistant lives. Baked in at build time — a static export has no runtime
 *  configuration — with an override for local development against a dev backend. */
const API = process.env.NEXT_PUBLIC_ASTRA_API_URL || site.apiUrl;

const UNREACHABLE =
  "I can't reach the assistant right now. Please use the contact form or email " +
  "sales@technomateai.com and someone from the team will get back to you.";

export function SupportChat() {
  const [open, setOpen] = useState(false);
  const [turns, setTurns] = useState<Turn[]>([GREETING]);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [showContact, setShowContact] = useState(false);

  const endRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns, sending, open]);

  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);

  useEffect(() => {
    if (!open) return;
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  async function send(question: string) {
    const message = question.trim();
    if (!message || sending) return;

    const history = turns
      .filter((turn) => turn !== GREETING)
      .map(({ role, content }) => ({ role, content }));

    setDraft("");
    setTurns((prior) => [...prior, { role: "user", content: message }]);
    setSending(true);
    setShowContact(false);

    try {
      const response = await fetch(`${API}/api/v1/public/assistant`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, history }),
      });
      const data = await response.json().catch(() => null);

      if (!response.ok || !data?.answer) {
        // 429 included: the server's own wording explains the wait better than a generic
        // failure would, so it is preferred when there is one.
        const detail = typeof data?.detail === "string" ? data.detail : UNREACHABLE;
        setTurns((prior) => [...prior, { role: "assistant", content: detail }]);
        setShowContact(true);
        return;
      }

      setTurns((prior) => [...prior, { role: "assistant", content: data.answer }]);
      // A question the documentation could not answer is a person who should be talking
      // to sales — and, read in aggregate, a gap in the FAQ worth filling.
      setShowContact(data.grounded === false);
      trackEvent("site_assistant_question", { grounded: data.grounded !== false });
    } catch {
      setTurns((prior) => [...prior, { role: "assistant", content: UNREACHABLE }]);
      setShowContact(true);
    } finally {
      setSending(false);
    }
  }

  if (!open) {
    return (
      <button
        onClick={() => {
          setOpen(true);
          trackEvent("site_assistant_open", {});
        }}
        aria-label="Ask about ASTRA"
        className="fixed bottom-5 right-5 z-50 flex items-center gap-2 rounded-full bg-brand-600 pl-4 pr-5 py-3 text-sm font-semibold text-white shadow-xl shadow-brand-600/25 transition hover:bg-brand-500"
      >
        <MessageSquare className="h-4 w-4" />
        Ask about Astra
      </button>
    );
  }

  return (
    <div
      role="dialog"
      aria-label="Ask about ASTRA"
      className="fixed bottom-5 right-5 z-50 flex w-[min(23rem,calc(100vw-2.5rem))] h-[min(32rem,calc(100vh-6rem))] flex-col overflow-hidden rounded-2xl border border-token bg-surface shadow-2xl"
    >
      <header className="flex shrink-0 items-center gap-2 border-b border-token px-4 py-3">
        <span className="rounded-lg bg-brand-500/10 p-1.5 text-brand-500">
          <Sparkles className="h-4 w-4" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-semibold text-primary-token">
            Ask about {site.product}
          </p>
          <p className="text-[11px] text-muted-token">
            Answers from our documentation and FAQ
          </p>
        </div>
        <button onClick={() => setOpen(false)} aria-label="Close">
          <X className="h-4 w-4 text-muted-token" />
        </button>
      </header>

      <div className="flex-1 space-y-3 overflow-y-auto px-4 py-3">
        {turns.map((turn, index) => (
          <div
            key={index}
            className={turn.role === "user" ? "flex justify-end" : "flex justify-start"}
          >
            <p
              className={
                turn.role === "user"
                  ? "max-w-[85%] whitespace-pre-wrap rounded-xl bg-brand-600 px-3 py-2 text-sm leading-relaxed text-white"
                  : "max-w-[85%] whitespace-pre-wrap rounded-xl border border-token bg-app px-3 py-2 text-sm leading-relaxed text-primary-token"
              }
            >
              {turn.content}
            </p>
          </div>
        ))}

        {turns.length === 1 && (
          <div className="flex flex-wrap gap-1.5 pt-1">
            {SUGGESTIONS.map((suggestion) => (
              <button
                key={suggestion}
                onClick={() => send(suggestion)}
                className="rounded-lg border border-token px-2.5 py-1.5 text-left text-xs text-secondary-token transition hover:border-brand-500 hover:text-brand-500"
              >
                {suggestion}
              </button>
            ))}
          </div>
        )}

        {sending && (
          <p className="inline-flex items-center gap-2 text-xs text-muted-token">
            <Loader2 className="h-3 w-3 animate-spin" /> Checking the documentation…
          </p>
        )}

        {showContact && !sending && (
          <div className="flex flex-wrap gap-2 pt-1">
            <Link
              href="/contact"
              onClick={() => trackEvent("site_assistant_handoff", { to: "contact" })}
              className="rounded-lg bg-brand-600 px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-brand-500"
            >
              Message the team
            </Link>
            <a
              href={`tel:${site.contact.phone.replace(/\s+/g, "")}`}
              className="rounded-lg border border-token px-3 py-1.5 text-xs font-semibold text-secondary-token"
            >
              {site.contact.phone}
            </a>
          </div>
        )}
        <div ref={endRef} />
      </div>

      <form
        onSubmit={(event) => {
          event.preventDefault();
          send(draft);
        }}
        className="flex shrink-0 items-center gap-2 border-t border-token px-3 py-3"
      >
        <input
          ref={inputRef}
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          maxLength={1000}
          placeholder="Ask a question…"
          className="flex-1 rounded-lg border border-token bg-app px-3 py-2 text-sm text-primary-token placeholder:text-muted-token focus:border-brand-500 focus:outline-none"
        />
        <button
          type="submit"
          disabled={!draft.trim() || sending}
          aria-label="Send"
          className="rounded-lg bg-brand-600 p-2 text-white transition hover:bg-brand-500 disabled:opacity-40"
        >
          <Send className="h-4 w-4" />
        </button>
      </form>
    </div>
  );
}
