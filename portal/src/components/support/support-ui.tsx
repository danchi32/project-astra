"use client";
/**
 * Shared furniture for support threads.
 *
 * The customer and the operator look at the same conversation from opposite sides, so the
 * thread, the status vocabulary and the diagnostics panel are built once. If they were
 * built twice they would drift, and the two sides disagreeing about what "resolved" looks
 * like is exactly the kind of thing that erodes trust in a support channel.
 */
import type { ReactNode } from "react";
import { Bot, CircleUser, ShieldCheck } from "lucide-react";
import type {
  SupportMessage, SupportRequestPriority, SupportRequestStatus,
} from "@/lib/api/types";
import { formatRelativeTime } from "@/lib/utils";

const STATUS: Record<SupportRequestStatus, { label: string; color: string; hint: string }> = {
  open: { label: "Open", color: "var(--health-warn)", hint: "Waiting on ASTRA" },
  in_progress: { label: "In progress", color: "var(--accent)", hint: "Being worked on" },
  waiting_customer: { label: "Waiting on you", color: "var(--accent)", hint: "ASTRA has replied" },
  resolved: { label: "Resolved", color: "var(--health-good)", hint: "Fixed" },
  closed: { label: "Closed", color: "var(--text-secondary)", hint: "No further action" },
};

const PRIORITY: Record<SupportRequestPriority, { label: string; color: string }> = {
  low: { label: "Low", color: "var(--text-secondary)" },
  normal: { label: "Normal", color: "var(--text-secondary)" },
  high: { label: "High", color: "var(--health-warn)" },
  urgent: { label: "Urgent", color: "var(--health-bad)" },
};

export const STATUS_ORDER: SupportRequestStatus[] = [
  "open", "in_progress", "waiting_customer", "resolved", "closed",
];

/** Two states read differently depending on which side of the thread you are on. Resolved
 *  here so a filter chip and the row it filters can never disagree. */
const OPERATOR_LABEL: Partial<Record<SupportRequestStatus, string>> = {
  open: "Needs a reply",
  waiting_customer: "Waiting on customer",
};

export function statusLabel(
  status: SupportRequestStatus, perspective: "customer" | "operator" = "customer",
): string {
  if (perspective === "operator") return OPERATOR_LABEL[status] ?? STATUS[status].label;
  return STATUS[status].label;
}

/** Status as word + colour, never colour alone. */
export function StatusPill({
  status, perspective = "customer",
}: { status: SupportRequestStatus; perspective?: "customer" | "operator" }) {
  const s = STATUS[status];
  const label = statusLabel(status, perspective);
  return (
    <span
      className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium whitespace-nowrap"
      style={{ color: s.color, background: `color-mix(in srgb, ${s.color} 12%, transparent)` }}
      title={s.hint}
    >
      {label}
    </span>
  );
}

export function PriorityPill({ priority }: { priority: SupportRequestPriority }) {
  const p = PRIORITY[priority];
  if (priority === "normal" || priority === "low") {
    return <span className="text-xs" style={{ color: p.color }}>{p.label}</span>;
  }
  return (
    <span
      className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium"
      style={{ color: p.color, background: `color-mix(in srgb, ${p.color} 12%, transparent)` }}
    >
      {p.label}
    </span>
  );
}

/** One conversation, oldest first. Operator messages are visually distinct so nobody has
 *  to read the byline to know who is talking. */
export function MessageThread({ messages }: { messages: SupportMessage[] }) {
  if (messages.length === 0) {
    return (
      <p className="text-sm py-6 text-center" style={{ color: "var(--text-secondary)" }}>
        No messages yet.
      </p>
    );
  }
  return (
    <ul className="flex flex-col gap-3">
      {messages.map((m) => (
        <li key={m.id} className="flex gap-2.5">
          <span
            className="p-1.5 rounded-lg shrink-0 h-fit"
            style={{
              background: m.from_operator
                ? "color-mix(in srgb, var(--accent) 12%, transparent)"
                : "var(--bg)",
              color: m.from_operator ? "var(--accent)" : "var(--text-secondary)",
              border: m.from_operator ? "none" : "1px solid var(--border)",
            }}
          >
            {m.from_operator ? <ShieldCheck size={14} /> : <CircleUser size={14} />}
          </span>
          <div className="min-w-0 flex-1">
            <div className="flex items-baseline gap-2 flex-wrap">
              <span className="text-xs font-medium" style={{ color: "var(--text-primary)" }}>
                {m.from_operator ? "ASTRA support" : (m.author_email ?? "Someone at your organization")}
              </span>
              <span className="text-xs" style={{ color: "var(--text-secondary)" }}>
                {formatRelativeTime(m.created_at)}
              </span>
            </div>
            <p
              className="text-sm mt-1 whitespace-pre-wrap break-words"
              style={{ color: "var(--text-primary)" }}
            >
              {m.body}
            </p>
          </div>
        </li>
      ))}
    </ul>
  );
}

const DIAGNOSTIC_LABELS: Record<string, string> = {
  plan: "Plan",
  subscription_status: "Subscription",
  licenses: "Licensed seats",
  devices_total: "Devices",
  devices_online: "Online at the time",
  devices_offline: "Offline at the time",
  remediations_total: "Fixes run",
  remediations_failed: "Fixes failed",
};

/**
 * What was collected and sent with the request.
 *
 * Shown to the customer as well as the operator, deliberately. A support form that quietly
 * attaches a snapshot of your fleet is a support form nobody should trust — so the same
 * panel appears on both sides, saying the same thing.
 */
export function DiagnosticsPanel({ diagnostics }: { diagnostics: Record<string, unknown> | null }) {
  if (!diagnostics) return null;
  const versions = diagnostics.agent_versions as Record<string, number> | undefined;
  const captured = diagnostics.captured_at as string | undefined;

  return (
    <div
      className="rounded-lg p-3"
      style={{ background: "var(--bg)", border: "1px solid var(--border)" }}
    >
      <div className="flex items-center gap-1.5 mb-2">
        <Bot size={13} style={{ color: "var(--text-secondary)" }} />
        <p className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>
          Collected automatically{captured ? ` — ${formatRelativeTime(captured)}` : ""}
        </p>
      </div>
      <dl className="grid grid-cols-2 sm:grid-cols-4 gap-x-4 gap-y-2">
        {Object.entries(DIAGNOSTIC_LABELS).map(([key, label]) => {
          const value = diagnostics[key];
          if (value === null || value === undefined) return null;
          return (
            <div key={key}>
              <dt className="text-xs" style={{ color: "var(--text-secondary)" }}>{label}</dt>
              <dd
                className="text-sm font-medium tabular-nums capitalize"
                style={{ color: "var(--text-primary)" }}
              >
                {String(value).replace(/_/g, " ")}
              </dd>
            </div>
          );
        })}
      </dl>
      {versions && Object.keys(versions).length > 0 && (
        <div className="mt-2 pt-2" style={{ borderTop: "1px solid var(--border)" }}>
          <p className="text-xs mb-1" style={{ color: "var(--text-secondary)" }}>
            Agent versions deployed
          </p>
          <div className="flex flex-wrap gap-1.5">
            {Object.entries(versions).map(([v, n]) => (
              <span
                key={v}
                className="text-xs px-2 py-0.5 rounded-full tabular-nums"
                style={{ background: "var(--surface)", border: "1px solid var(--border)", color: "var(--text-secondary)" }}
              >
                {v} × {n}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export function Panel({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div
      className={`rounded-xl p-5 ${className}`}
      style={{ background: "var(--surface)", border: "1px solid var(--border)" }}
    >
      {children}
    </div>
  );
}
