"use client";
import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Send, Sparkles, Search, ChevronDown } from "lucide-react";
import {
  createConversation,
  getMessages,
  listConversations,
  sendMessage,
} from "@/lib/api/conversations";
import type { Message } from "@/lib/api/types";

export default function AssistantPage() {
  const queryClient = useQueryClient();
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  const { data: conversations } = useQuery({
    queryKey: ["conversations"],
    queryFn: listConversations,
  });

  const { data: messages } = useQuery({
    queryKey: ["messages", conversationId],
    queryFn: () => (conversationId ? getMessages(conversationId) : Promise.resolve([])),
    enabled: !!conversationId,
  });

  // Auto-select the most recent conversation.
  useEffect(() => {
    if (!conversationId && conversations && conversations.length > 0) {
      setConversationId(conversations[0].id);
    }
  }, [conversations, conversationId]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, sending]);

  async function ensureConversation(): Promise<string> {
    if (conversationId) return conversationId;
    const conv = await createConversation("New conversation");
    setConversationId(conv.id);
    queryClient.invalidateQueries({ queryKey: ["conversations"] });
    return conv.id;
  }

  async function handleSend(e: React.FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text || sending) return;
    setInput("");
    setSending(true);
    try {
      const cid = await ensureConversation();
      await sendMessage(cid, text);
      await queryClient.invalidateQueries({ queryKey: ["messages", cid] });
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="flex flex-col h-[calc(100vh-3rem)]">
      {/* Header */}
      <div className="flex items-center gap-2 pb-4">
        <div className="p-2 rounded-lg" style={{ background: "rgba(37,99,235,0.1)", color: "var(--accent)" }}>
          <Sparkles size={18} />
        </div>
        <div>
          <h1 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>ASTRA Assistant</h1>
          <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
            AI system administrator — evidence-based device diagnostics
          </p>
        </div>
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto space-y-4 pb-4">
        {(!messages || messages.length === 0) && !sending && (
          <div className="h-full flex flex-col items-center justify-center text-center px-4">
            <Sparkles size={40} style={{ color: "var(--accent)", opacity: 0.4 }} />
            <p className="mt-4 text-sm font-medium" style={{ color: "var(--text-primary)" }}>
              Ask ASTRA about your devices
            </p>
            <p className="mt-1 text-xs max-w-sm" style={{ color: "var(--text-secondary)" }}>
              Try: &ldquo;Is the CPU health okay on our devices?&rdquo; — ASTRA will gather live
              telemetry before answering.
            </p>
          </div>
        )}
        {messages?.map((m) => <MessageBubble key={m.id} message={m} />)}
        {sending && (
          <div className="flex gap-3">
            <Avatar assistant />
            <div className="text-sm px-4 py-2.5 rounded-2xl animate-pulse" style={{ background: "var(--surface)", color: "var(--text-secondary)", border: "1px solid var(--border)" }}>
              Investigating…
            </div>
          </div>
        )}
      </div>

      {/* Composer */}
      <form onSubmit={handleSend} className="flex gap-2 pt-2" style={{ borderTop: "1px solid var(--border)" }}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about a device's health, performance, or errors…"
          className="flex-1 px-4 py-2.5 rounded-xl text-sm outline-none focus:ring-2 focus:ring-blue-500"
          style={{ background: "var(--surface)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
        />
        <button
          type="submit"
          disabled={sending || !input.trim()}
          className="px-4 rounded-xl text-white transition-opacity disabled:opacity-40"
          style={{ background: "var(--accent)" }}
        >
          <Send size={16} />
        </button>
      </form>
    </div>
  );
}

function Avatar({ assistant }: { assistant?: boolean }) {
  return (
    <div className="w-8 h-8 rounded-full flex items-center justify-center shrink-0 text-xs font-semibold"
      style={{
        background: assistant ? "rgba(37,99,235,0.1)" : "var(--border)",
        color: assistant ? "var(--accent)" : "var(--text-secondary)",
      }}>
      {assistant ? <Sparkles size={14} /> : "You"}
    </div>
  );
}

function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === "user";
  return (
    <div className={`flex gap-3 ${isUser ? "flex-row-reverse" : ""}`}>
      <Avatar assistant={!isUser} />
      <div className={`max-w-[75%] ${isUser ? "items-end" : ""}`}>
        <div
          className="text-sm px-4 py-2.5 rounded-2xl whitespace-pre-wrap"
          style={{
            background: isUser ? "var(--accent)" : "var(--surface)",
            color: isUser ? "#fff" : "var(--text-primary)",
            border: isUser ? "none" : "1px solid var(--border)",
          }}
        >
          {message.content}
        </div>
        {message.tool_trail && message.tool_trail.length > 0 && (
          <EvidenceTrail trail={message.tool_trail} />
        )}
      </div>
    </div>
  );
}

function EvidenceTrail({ trail }: { trail: NonNullable<Message["tool_trail"]> }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="mt-1.5">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-1 text-xs font-medium"
        style={{ color: "var(--text-secondary)" }}
      >
        <Search size={12} />
        {trail.length} evidence step{trail.length > 1 ? "s" : ""} gathered
        <ChevronDown size={12} className={open ? "rotate-180 transition-transform" : "transition-transform"} />
      </button>
      {open && (
        <div className="mt-1.5 space-y-1.5">
          {trail.map((step, i) => (
            <div key={i} className="text-xs rounded-lg p-2 font-mono overflow-x-auto"
              style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-secondary)" }}>
              <div style={{ color: "var(--accent)" }}>{step.tool}({JSON.stringify(step.input)})</div>
              <div className="mt-1 whitespace-pre-wrap break-all">{step.output.slice(0, 400)}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
