"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  LayoutDashboard, Monitor, Package, Users, Activity,
  BookOpen, Zap, BarChart3, Bell, Settings, LogOut, Shield, ShieldCheck,
  CreditCard, Building2, ScrollText,
} from "lucide-react";
import { logout, getMe } from "@/lib/api/auth";
import { getUnreadCount } from "@/lib/api/notifications";
import { useRouter } from "next/navigation";
import { getViewAs } from "@/lib/viewAs";

const NAV = [
  { href: "/dashboard", icon: LayoutDashboard, label: "Dashboard" },
  { href: "/devices", icon: Monitor, label: "Devices" },
  { href: "/assets", icon: Package, label: "Assets" },
  { href: "/users", icon: Users, label: "Users" },
  { href: "/telemetry", icon: Activity, label: "Telemetry" },
  { href: "/knowledge", icon: BookOpen, label: "Knowledge Base" },
  { href: "/self-healing", icon: Zap, label: "Self Healing" },
  { href: "/reports", icon: BarChart3, label: "Reports" },
  { href: "/notifications", icon: Bell, label: "Notifications" },
  { href: "/audit", icon: Shield, label: "Audit Logs" },
  { href: "/settings", icon: Settings, label: "Settings" },
];

// The operator console — business-focused sections spanning ALL organizations.
// A customer's own operational pages are reached via View-as.
const PLATFORM_NAV = [
  { href: "/platform", icon: ShieldCheck, label: "Overview" },
  { href: "/platform/organizations", icon: Building2, label: "Organizations" },
  { href: "/platform/billing", icon: CreditCard, label: "Billing" },
  { href: "/platform/reports", icon: BarChart3, label: "Reports" },
  { href: "/platform/audit", icon: ScrollText, label: "Audit trail" },
  { href: "/platform/knowledge", icon: BookOpen, label: "Global knowledge" },
  { href: "/platform/fixes", icon: Zap, label: "Auto-fixes" },
  { href: "/settings", icon: Settings, label: "Settings" },
];

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { data: unreadCount } = useQuery({
    queryKey: ["unread-notifications"],
    queryFn: getUnreadCount,
    refetchInterval: 30_000,
  });
  const { data: me } = useQuery({ queryKey: ["me"], queryFn: getMe });

  // "View as organization": while active, the operator browses the VIEWED org, so
  // they need the org nav — not the platform nav. Track it live (same-tab event +
  // cross-tab storage), and trust the server's view_as flag as well.
  const [viewAsActive, setViewAsActive] = useState(false);
  useEffect(() => {
    const sync = () => setViewAsActive(getViewAs() !== null);
    sync();
    window.addEventListener("viewas-change", sync);
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener("viewas-change", sync);
      window.removeEventListener("storage", sync);
    };
  }, []);
  const inViewAs = viewAsActive || !!me?.view_as;

  // In view-as: the org nav (read-only browsing, incl. Billing — the role is admin).
  // Platform operator: the operator console nav. Everyone else: their org's nav.
  const nav = inViewAs
    ? [...NAV, { href: "/billing", icon: CreditCard, label: "Billing" }]
    : me?.is_platform_admin
      ? PLATFORM_NAV
      : [
          ...NAV,
          ...(me?.role === "admin" ? [{ href: "/billing", icon: CreditCard, label: "Billing" }] : []),
        ];

  async function handleLogout() {
    await logout();
    router.push("/login");
  }

  return (
    <aside
      className="flex flex-col w-56 h-screen py-4 shrink-0"
      style={{ background: "var(--surface)", borderRight: "1px solid var(--border)" }}
    >
      {/* Logo */}
      <div className="px-5 pb-6 shrink-0 flex items-center gap-2 text-lg font-bold" style={{ color: "var(--accent)" }}>
        <span className="text-2xl">⬡</span> ASTRA
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto px-2 space-y-0.5">
        {nav.map(({ href, icon: Icon, label }) => {
          // Exact match for /platform (so its sub-pages don't also light it up);
          // prefix match elsewhere so detail pages keep their parent highlighted.
          const active = href === "/platform" ? pathname === "/platform" : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors"
              style={{
                background: active ? "rgba(37,99,235,0.1)" : "transparent",
                color: active ? "var(--accent)" : "var(--text-secondary)",
              }}
            >
              <Icon size={16} />
              <span className="flex-1">{label}</span>
              {href === "/notifications" && !!unreadCount && (
                <span
                  className="text-xs font-semibold px-1.5 py-0.5 rounded-full leading-none"
                  style={{ background: "#ef4444", color: "white" }}
                >
                  {unreadCount > 99 ? "99+" : unreadCount}
                </span>
              )}
            </Link>
          );
        })}
      </nav>

      {/* Logout */}
      <div className="px-2 mt-4 shrink-0">
        <button
          onClick={handleLogout}
          className="flex items-center gap-3 w-full px-3 py-2 rounded-lg text-sm font-medium transition-colors hover:bg-red-500/10 hover:text-red-500"
          style={{ color: "var(--text-secondary)" }}
        >
          <LogOut size={16} /> Sign out
        </button>
      </div>
    </aside>
  );
}
