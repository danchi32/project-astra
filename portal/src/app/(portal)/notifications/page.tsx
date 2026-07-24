"use client";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { Bell, CheckCheck, AlertTriangle, AlertOctagon, Info } from "lucide-react";
import { listNotifications, markNotificationRead, markAllNotificationsRead } from "@/lib/api/notifications";
import type { Notification, NotificationSeverity } from "@/lib/api/types";

const SEVERITY_STYLE: Record<NotificationSeverity, { color: string; icon: typeof Info }> = {
  info: { color: "#b246d4", icon: Info },
  warning: { color: "#f59e0b", icon: AlertTriangle },
  critical: { color: "#ef4444", icon: AlertOctagon },
};

function timeAgo(iso: string): string {
  const seconds = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function NotificationRow({ n, onRead }: { n: Notification; onRead: (id: string) => void }) {
  const { color, icon: Icon } = SEVERITY_STYLE[n.severity];
  const content = (
    <div
      className="flex items-start gap-3 px-4 py-3"
      style={{ background: n.is_read ? "transparent" : "rgba(154,47,187,0.04)" }}
    >
      <div className="p-1.5 rounded-full shrink-0" style={{ background: `${color}1a`, color }}>
        <Icon size={16} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <p className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>{n.title}</p>
          {!n.is_read && <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: "var(--accent)" }} />}
        </div>
        <p className="text-sm mt-0.5" style={{ color: "var(--text-secondary)" }}>{n.message}</p>
        <p className="text-xs mt-1 capitalize" style={{ color: "var(--text-secondary)" }}>
          {n.category} · {timeAgo(n.created_at)}
        </p>
      </div>
      {!n.is_read && (
        <button
          onClick={(e) => { e.preventDefault(); onRead(n.id); }}
          className="text-xs font-medium shrink-0 px-2 py-1 rounded-lg"
          style={{ color: "var(--accent)" }}
        >
          Mark read
        </button>
      )}
    </div>
  );
  return n.link ? (
    <Link href={n.link} onClick={() => !n.is_read && onRead(n.id)} className="block hover:bg-black/[0.02]">
      {content}
    </Link>
  ) : (
    <div>{content}</div>
  );
}

export default function NotificationsPage() {
  const queryClient = useQueryClient();
  const [unreadOnly, setUnreadOnly] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["notifications", unreadOnly],
    queryFn: () => listNotifications(unreadOnly),
  });

  async function refresh() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["notifications"] }),
      queryClient.invalidateQueries({ queryKey: ["unread-notifications"] }),
    ]);
  }

  async function handleRead(id: string) {
    await markNotificationRead(id);
    await refresh();
  }

  async function handleReadAll() {
    await markAllNotificationsRead();
    await refresh();
  }

  const unreadTotal = data?.filter((n) => !n.is_read).length ?? 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="p-2 rounded-lg" style={{ background: "rgba(154,47,187,0.1)", color: "var(--accent)" }}>
            <Bell size={18} />
          </div>
          <div>
            <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>Notifications</h1>
            <p className="text-sm mt-0.5" style={{ color: "var(--text-secondary)" }}>
              Alerts from remediation approvals and failures across your fleet
            </p>
          </div>
        </div>
        {unreadTotal > 0 && (
          <button onClick={handleReadAll}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium"
            style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }}>
            <CheckCheck size={14} /> Mark all read
          </button>
        )}
      </div>

      <div className="flex gap-1 p-1 rounded-lg w-fit" style={{ background: "var(--bg)", border: "1px solid var(--border)" }}>
        <button onClick={() => setUnreadOnly(false)}
          className="px-3 py-1.5 rounded-md text-sm font-medium"
          style={!unreadOnly ? { background: "var(--accent)", color: "white" } : { color: "var(--text-secondary)" }}>
          All
        </button>
        <button onClick={() => setUnreadOnly(true)}
          className="px-3 py-1.5 rounded-md text-sm font-medium"
          style={unreadOnly ? { background: "var(--accent)", color: "white" } : { color: "var(--text-secondary)" }}>
          Unread
        </button>
      </div>

      <div className="rounded-xl overflow-hidden divide-y" style={{ border: "1px solid var(--border)", background: "var(--surface)" }}>
        {isLoading && <p className="px-4 py-10 text-center text-sm" style={{ color: "var(--text-secondary)" }}>Loading…</p>}
        {!isLoading && !data?.length && (
          <p className="px-4 py-10 text-center text-sm" style={{ color: "var(--text-secondary)" }}>
            {unreadOnly ? "No unread notifications." : "No notifications yet."}
          </p>
        )}
        {data?.map((n) => (
          <div key={n.id} style={{ borderColor: "var(--border)" }}>
            <NotificationRow n={n} onRead={handleRead} />
          </div>
        ))}
      </div>
    </div>
  );
}
