"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard, Monitor, Package, Users, Activity,
  BookOpen, Zap, BarChart3, Bell, Settings, LogOut, Shield, Sparkles,
} from "lucide-react";
import { logout } from "@/lib/api/auth";
import { useRouter } from "next/navigation";

const NAV = [
  { href: "/dashboard", icon: LayoutDashboard, label: "Dashboard" },
  { href: "/assistant", icon: Sparkles, label: "AI Assistant" },
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

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();

  async function handleLogout() {
    await logout();
    router.push("/login");
  }

  return (
    <aside
      className="flex flex-col w-56 min-h-screen py-4 shrink-0"
      style={{ background: "var(--surface)", borderRight: "1px solid var(--border)" }}
    >
      {/* Logo */}
      <div className="px-5 pb-6 flex items-center gap-2 text-lg font-bold" style={{ color: "var(--accent)" }}>
        <span className="text-2xl">⬡</span> ASTRA
      </div>

      {/* Nav */}
      <nav className="flex-1 px-2 space-y-0.5">
        {NAV.map(({ href, icon: Icon, label }) => {
          const active = pathname.startsWith(href);
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
              {label}
            </Link>
          );
        })}
      </nav>

      {/* Logout */}
      <div className="px-2 mt-4">
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
