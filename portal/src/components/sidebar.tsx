"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  LayoutDashboard, Monitor, Users, Radar, Boxes, MonitorSmartphone,
  BookOpen, Zap, BarChart3, Shield, ShieldCheck,
  CreditCard, Building2, ScrollText, LifeBuoy,
} from "lucide-react";
import { getMe } from "@/lib/api/auth";
import { getViewAs } from "@/lib/viewAs";

const NAV = [
  { href: "/dashboard", icon: LayoutDashboard, label: "Dashboard" },
  { href: "/devices", icon: Monitor, label: "Devices" },
  { href: "/sessions", icon: MonitorSmartphone, label: "Sessions" },
  { href: "/groups", icon: Boxes, label: "Groups & Teams" },
  { href: "/compliance", icon: ShieldCheck, label: "Compliance" },
  { href: "/fleet", icon: Radar, label: "Fleet Issues" },
  { href: "/users", icon: Users, label: "Users" },
  { href: "/knowledge", icon: BookOpen, label: "Knowledge Base" },
  { href: "/self-healing", icon: Zap, label: "Self Healing" },
  { href: "/reports", icon: BarChart3, label: "Reports" },
  { href: "/audit", icon: Shield, label: "Audit Logs" },
  // Notifications, Settings, Help & Support and Sign out are not here any more — they moved
  // to the top bar's icon strip and profile menu, where they are the same on every page and
  // don't scroll away at the foot of a long nav.
];

// The operator console — business-focused sections spanning ALL organizations.
// A customer's own operational pages are reached via View-as.
const PLATFORM_NAV = [
  { href: "/platform", icon: ShieldCheck, label: "Overview" },
  { href: "/platform/organizations", icon: Building2, label: "Organizations" },
  { href: "/platform/billing", icon: CreditCard, label: "Billing" },
  { href: "/platform/support", icon: LifeBuoy, label: "Support queue" },
  { href: "/platform/reports", icon: BarChart3, label: "Reports" },
  { href: "/platform/audit", icon: ScrollText, label: "Audit trail" },
  { href: "/platform/knowledge", icon: BookOpen, label: "Global knowledge" },
  { href: "/platform/fixes", icon: Zap, label: "Auto-fixes" },
  // Settings moved to the top bar's profile menu (see NAV above).
];

export function Sidebar() {
  const pathname = usePathname();
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
                background: active ? "rgba(154,47,187,0.1)" : "transparent",
                color: active ? "var(--accent)" : "var(--text-secondary)",
              }}
            >
              <Icon size={16} />
              <span className="flex-1">{label}</span>
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
