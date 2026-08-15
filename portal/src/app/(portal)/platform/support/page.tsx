"use client";
/**
 * The support queue, from ASTRA's side.
 *
 * Ordered by whose turn it is rather than by age — a three-week-old thread parked on the
 * customer is not the oldest thing we owe anybody. The diagnostics panel is what stops
 * this becoming a game of twenty questions: the fleet's state at the moment they asked is
 * already on the thread.
 */
import { useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ExternalLink, LifeBuoy, Send } from "lucide-react";
import { getMe } from "@/lib/api/auth";
import {
  getPlatformSupportRequest, getSupportQueue, replyAsOperator, updateSupportRequest,
} from "@/lib/api/platform";
import type { SupportRequestPriority, SupportRequestStatus } from "@/lib/api/types";
import { formatRelativeTime } from "@/lib/utils";
import { Kpi, SectionHeading } from "@/components/platform/console-ui";
import {
  DiagnosticsPanel, MessageThread, Panel, PriorityPill, STATUS_ORDER, StatusPill, statusLabel,
} from "@/components/support/support-ui";

const REFETCH = 30_000;

export default function PlatformSupportPage() {
  const { data: me } = useQuery({ queryKey: ["me"], queryFn: getMe });
  const enabled = !!me?.is_platform_admin;
  const [filter, setFilter] = useState<SupportRequestStatus | null>(null);
  const [openId, setOpenId] = useState<string | null>(null);

  const { data: queue, isLoading } = useQuery({
    queryKey: ["support-queue", filter],
    queryFn: () => getSupportQueue(filter ? { request_status: filter } : {}),
    enabled,
    refetchInterval: REFETCH,
  });

  if (me && !me.is_platform_admin) {
    return (
      <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
        Platform administrator access required.
      </p>
    );
  }

  if (openId) return <OperatorThread id={openId} onBack={() => setOpenId(null)} />;

  const counts = queue?.counts_by_status ?? {};
  const needsReply = (counts.open ?? 0) + (counts.in_progress ?? 0);

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
              Support queue
            </h1>
            <p className="text-sm mt-0.5" style={{ color: "var(--text-secondary)" }}>
              Customers asking ASTRA for help — ours first
            </p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Kpi
          label="Needs a reply" value={needsReply}
          tone={needsReply > 0 ? "warn" : "good"}
          hint="Open or in progress"
        />
        <Kpi label="Waiting on customer" value={counts.waiting_customer ?? 0} hint="We answered" />
        <Kpi label="Resolved" value={counts.resolved ?? 0} hint="Fixed and told" />
        <Kpi label="Closed" value={counts.closed ?? 0} hint="No further action" />
      </div>

      <div>
        <SectionHeading
          title="Threads"
          description="Whose turn it is, then priority, then how long it has waited"
        />

        <div className="flex items-center gap-1.5 flex-wrap mb-3">
          <FilterChip active={filter === null} onClick={() => setFilter(null)} label="All" />
          {STATUS_ORDER.map((s) => (
            <FilterChip
              key={s}
              active={filter === s}
              onClick={() => setFilter(filter === s ? null : s)}
              label={statusLabel(s, "operator")}
              count={counts[s]}
            />
          ))}
        </div>

        {isLoading ? (
          <Panel><div className="h-32 animate-pulse rounded-lg" style={{ background: "var(--bg)" }} /></Panel>
        ) : (queue?.requests.length ?? 0) === 0 ? (
          <Panel>
            <p className="text-sm text-center py-8" style={{ color: "var(--text-secondary)" }}>
              Nothing here — no customer is waiting on us.
            </p>
          </Panel>
        ) : (
          <div className="rounded-xl overflow-hidden" style={{ border: "1px solid var(--border)" }}>
            <ul style={{ background: "var(--surface)" }}>
              {queue?.requests.map((r) => (
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
                        {r.org_name ?? "Unknown organization"}
                        {r.last_reply_at ? ` · ${formatRelativeTime(r.last_reply_at)}` : ""}
                        {r.category ? ` · ${r.category}` : ""}
                      </span>
                    </div>
                    <PriorityPill priority={r.priority} />
                    <StatusPill status={r.status} perspective="operator" />
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}

function FilterChip({ active, onClick, label, count }: {
  active: boolean; onClick: () => void; label: string; count?: number;
}) {
  return (
    <button
      onClick={onClick}
      className="px-2.5 py-1 rounded-lg text-xs font-medium transition-colors"
      style={{
        background: active ? "color-mix(in srgb, var(--accent) 12%, transparent)" : "transparent",
        color: active ? "var(--accent)" : "var(--text-secondary)",
        border: `1px solid ${active ? "var(--accent)" : "var(--border)"}`,
      }}
    >
      {label}
      {count != null && <span className="ml-1.5 tabular-nums opacity-70">{count}</span>}
    </button>
  );
}

function OperatorThread({ id, onBack }: { id: string; onBack: () => void }) {
  const [reply, setReply] = useState("");
  const queryClient = useQueryClient();

  const { data: request } = useQuery({
    queryKey: ["platform-support-request", id],
    queryFn: () => getPlatformSupportRequest(id),
    refetchInterval: REFETCH,
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["platform-support-request", id] });
    queryClient.invalidateQueries({ queryKey: ["support-queue"] });
  };

  const replyMutation = useMutation({
    mutationFn: () => replyAsOperator(id, reply),
    onSuccess: () => { setReply(""); invalidate(); },
  });
  const updateMutation = useMutation({
    mutationFn: (data: { status?: SupportRequestStatus; priority?: SupportRequestPriority }) =>
      updateSupportRequest(id, data),
    onSuccess: invalidate,
  });

  if (!request) {
    return <Panel><div className="h-32 animate-pulse rounded-lg" style={{ background: "var(--bg)" }} /></Panel>;
  }

  const control = {
    background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)",
  } as const;

  return (
    <div className="space-y-4">
      <button onClick={onBack} className="inline-flex items-center gap-1.5 text-xs"
        style={{ color: "var(--accent)" }}>
        <ArrowLeft size={13} /> Back to the queue
      </button>

      <Panel>
        <div className="flex items-start justify-between gap-3 flex-wrap">
          <div className="min-w-0">
            <h2 className="text-base font-semibold" style={{ color: "var(--text-primary)" }}>
              {request.subject}
            </h2>
            <p className="text-xs mt-0.5" style={{ color: "var(--text-secondary)" }}>
              <span className="font-mono">{request.reference}</span>
              {request.org_name ? ` · ${request.org_name}` : ""}
            </p>
          </div>
          {request.org_id && (
            <Link
              href={`/platform/${request.org_id}`}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium"
              style={{ border: "1px solid var(--border)", color: "var(--accent)" }}
            >
              Open account <ExternalLink size={12} />
            </Link>
          )}
        </div>

        {/* Triage controls. Status also moves on its own when either side writes — this is
            for the cases that need a human decision. */}
        <div className="flex items-center gap-2 mt-4 flex-wrap">
          <select
            value={request.status}
            onChange={(e) => updateMutation.mutate({ status: e.target.value as SupportRequestStatus })}
            className="px-2.5 py-1.5 rounded-lg text-xs outline-none"
            style={control}
          >
            {STATUS_ORDER.map((s) => (
              <option key={s} value={s}>{statusLabel(s, "operator")}</option>
            ))}
          </select>
          <select
            value={request.priority}
            onChange={(e) => updateMutation.mutate({ priority: e.target.value as SupportRequestPriority })}
            className="px-2.5 py-1.5 rounded-lg text-xs outline-none capitalize"
            style={control}
          >
            {(["low", "normal", "high", "urgent"] as const).map((p) => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>
          {updateMutation.isPending && (
            <span className="text-xs" style={{ color: "var(--text-secondary)" }}>Saving…</span>
          )}
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
          onSubmit={(e) => { e.preventDefault(); if (reply.trim()) replyMutation.mutate(); }}
        >
          <textarea
            value={reply}
            onChange={(e) => setReply(e.target.value)}
            rows={4}
            maxLength={10000}
            placeholder="Reply to the customer…"
            className="w-full px-3 py-2 rounded-lg text-sm outline-none resize-y"
            style={control}
          />
          <div className="flex items-center gap-2">
            <button
              type="submit"
              disabled={!reply.trim() || replyMutation.isPending}
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50"
              style={{ background: "var(--accent)" }}
            >
              <Send size={14} /> {replyMutation.isPending ? "Sending…" : "Send reply"}
            </button>
            <span className="text-xs" style={{ color: "var(--text-secondary)" }}>
              Replying notifies them and hands the thread back.
            </span>
          </div>
        </form>
      </Panel>
    </div>
  );
}
