"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  LayoutDashboard, Monitor, Users, Radar, Boxes,
  BookOpen, Zap, BarChart3, Shield, ShieldCheck,
  CreditCard, Building2, ScrollText, LifeBuoy, Bot, Clock, Lock,
  ChevronRight, ChevronDown } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { getMe } from "@/lib/api/auth";
import { getViewAs } from "@/lib/viewAs";
import { SavioLogo } from "@/components/savio-mark";

// A sidebar entry is either a plain LINK (common, top-level) or a GROUP that expands to its own
// sub-items — the same shape the Tracker uses, now applied across the app. Groups collect the
// pages that belong to one job; the common pages (Dashboard, Users, Groups & Teams, Reports,
// Audit, Billing) stay flat and outside the groups.
type NavLink = { href: string; icon: LucideIcon; label: string };
type NavChild = { href: string; label: string };
type NavGroup = {
  group: string;
  icon: LucideIcon;
  children: NavChild[];
  // A group gated on an entitlement (Tracker): locked until the org subscribes. Its header then
  // links to the first child, which shows the upgrade prompt, instead of expanding.
  feature?: string;
  lockedHref?: string;
};
type NavEntry = NavLink | NavGroup;

const isGroup = (e: NavEntry): e is NavGroup => "group" in e;

// The Tracker's own sections — one group among several now.
const TRACKER_SUBNAV: NavChild[] = [
  { href: "/tracker", label: "Dashboard" },
  { href: "/tracker/attendance", label: "Attendance" },
  // "Employees" / "Departments" rather than "Users" / "Teams": the org-wide Users and
  // Groups & Teams are common top-level items, and the Tracker's own per-person and
  // per-team views are a different thing — the workforce names keep them from reading as
  // duplicates of those.
  { href: "/tracker/users", label: "Employees" },
  { href: "/tracker/teams", label: "Departments" },
  { href: "/tracker/shifts", label: "Shifts" },
  { href: "/tracker/configuration", label: "Configuration" },
];

const ORG_NAV: NavEntry[] = [
  { href: "/dashboard", icon: LayoutDashboard, label: "Dashboard" },
  // Common management pages, kept flat and above the functional groups.
  { href: "/users", icon: Users, label: "Users" },
  { href: "/groups", icon: Boxes, label: "Groups & Teams" },
  { group: "Endpoints", icon: Monitor, children: [
    { href: "/devices", label: "Devices" },
    { href: "/sessions", label: "Sessions" },
  ] },
  { group: "Operations", icon: Radar, children: [
    { href: "/fleet", label: "Fleet Issues" },
    { href: "/self-healing", label: "Self Healing" },
    { href: "/compliance", label: "Compliance" },
  ] },
  { group: "AI", icon: Bot, children: [
    { href: "/assistants", label: "Assistants" },
    { href: "/knowledge", label: "Knowledge Base" },
  ] },
  { group: "Tracker", icon: Clock, feature: "workforce_insights", lockedHref: "/tracker",
    children: TRACKER_SUBNAV },
  // The rest of the common pages.
  { href: "/reports", icon: BarChart3, label: "Reports" },
  { href: "/audit", icon: Shield, label: "Audit Logs" },
];

const BILLING: NavLink = { href: "/billing", icon: CreditCard, label: "Billing" };

// The operator console — business-focused sections spanning ALL organizations. Left flat; a
// customer's own operational pages are reached via View-as.
const PLATFORM_NAV: NavLink[] = [
  { href: "/platform", icon: ShieldCheck, label: "Overview" },
  { href: "/platform/organizations", icon: Building2, label: "Organizations" },
  { href: "/platform/billing", icon: CreditCard, label: "Billing" },
  { href: "/platform/support", icon: LifeBuoy, label: "Support queue" },
  { href: "/platform/reports", icon: BarChart3, label: "Reports" },
  { href: "/platform/audit", icon: ScrollText, label: "Audit trail" },
  { href: "/platform/knowledge", icon: BookOpen, label: "Global knowledge" },
  { href: "/platform/fixes", icon: Zap, label: "Auto-fixes" },
];

const linkStyle = (active: boolean) => ({
  background: active ? "rgba(37,99,235,0.1)" : "transparent",
  color: active ? "var(--accent)" : "var(--text-secondary)",
});

export function Sidebar() {
  const pathname = usePathname();
  const { data: me } = useQuery({ queryKey: ["me"], queryFn: getMe });

  // "View as organization": while active, the operator browses the VIEWED org, so they need the
  // org nav — not the platform nav. Track it live (same-tab event + cross-tab storage).
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

  // Groups the user has expanded by hand, on top of the one that auto-opens for the active route.
  const [openGroups, setOpenGroups] = useState<Record<string, boolean>>({});
  const toggle = (label: string) =>
    setOpenGroups((o) => ({ ...o, [label]: !o[label] }));

  // Prefix-active: the page itself or anything beneath it (so a detail page keeps its parent lit).
  // "/platform" is matched exactly so its sub-pages don't also light up the Overview entry.
  const isActive = (href: string) =>
    href === "/platform" ? pathname === "/platform" : pathname === href || pathname.startsWith(href + "/");

  const platform = me?.is_platform_admin && !inViewAs;
  const nav: NavEntry[] = platform
    ? PLATFORM_NAV
    : [...ORG_NAV, ...(inViewAs || me?.role === "admin" ? [BILLING] : [])];

  function renderLink({ href, icon: Icon, label }: NavLink) {
    const active = isActive(href);
    return (
      <Link
        key={href}
        href={href}
        className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors"
        style={linkStyle(active)}
      >
        <Icon size={16} />
        <span className="flex-1">{label}</span>
      </Link>
    );
  }

  function renderGroup(g: NavGroup) {
    const Icon = g.icon;
    const locked = g.feature !== undefined
      && me?.entitlements !== undefined
      && !me.entitlements.includes(g.feature);

    // A locked group (Tracker without the subscription) is a single link to its upgrade prompt.
    if (locked && g.lockedHref) {
      return (
        <Link
          key={g.group}
          href={g.lockedHref}
          className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors"
          style={linkStyle(isActive(g.lockedHref))}
        >
          <Icon size={16} />
          <span className="flex-1">{g.group}</span>
          <Lock size={13} style={{ opacity: 0.6 }} />
        </Link>
      );
    }

    const groupActive = g.children.some((c) => isActive(c.href));
    const expanded = groupActive || !!openGroups[g.group];
    const Chevron = expanded ? ChevronDown : ChevronRight;
    return (
      <div key={g.group}>
        <button
          onClick={() => toggle(g.group)}
          className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors"
          style={linkStyle(groupActive)}
        >
          <Icon size={16} />
          <span className="flex-1 text-left">{g.group}</span>
          <Chevron size={14} style={{ opacity: 0.7 }} />
        </button>
        {expanded && (
          <div className="mt-0.5 mb-1 ml-5 pl-3 space-y-0.5" style={{ borderLeft: "1px solid var(--border)" }}>
            {g.children.map((c) => {
              const active = isActive(c.href);
              return (
                <Link
                  key={c.href}
                  href={c.href}
                  className="block px-3 py-1.5 rounded-lg text-sm transition-colors"
                  style={{ ...linkStyle(active), fontWeight: active ? 600 : 400 }}
                >
                  {c.label}
                </Link>
              );
            })}
          </div>
        )}
      </div>
    );
  }

  return (
    <aside
      className="flex flex-col w-56 h-screen py-4 shrink-0"
      style={{ background: "var(--surface)", borderRight: "1px solid var(--border)" }}
    >
      {/* Logo */}
      <div className="px-4 pb-6 shrink-0">
        <SavioLogo size={34} tagline="AI IT agent" />
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto px-2 space-y-0.5">
        {nav.map((entry) => (isGroup(entry) ? renderGroup(entry) : renderLink(entry)))}
      </nav>
    </aside>
  );
}
