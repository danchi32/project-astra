"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Clock } from "lucide-react";

/** The Tracker's section nav. Users (attendance + per-person drill-down), Teams (people grouped
 *  into departments, rolled up and measured against their shift), and Configuration (categories,
 *  shifts, and the rest of the setup). Rendered at the top of each top-level Tracker page so the
 *  three sections feel like one tool rather than three routes. */
const TABS = [
  { href: "/tracker", label: "Users" },
  { href: "/tracker/teams", label: "Teams" },
  { href: "/tracker/configuration", label: "Configuration" },
] as const;

export function TrackerTabs({ active }: { active: "users" | "teams" | "configuration" }) {
  const pathname = usePathname();
  // `active` is explicit so the per-user drill-down (/tracker/<user>) still highlights Users.
  const current =
    active === "users" ? "/tracker" : active === "teams" ? "/tracker/teams" : "/tracker/configuration";
  return (
    <div>
      <div className="flex items-center gap-2 mb-1">
        <div className="p-2 rounded-lg" style={{ background: "rgba(154,47,187,0.1)", color: "var(--accent)" }}>
          <Clock size={18} />
        </div>
        <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>Tracker</h1>
      </div>
      <nav className="flex gap-1 border-b" style={{ borderColor: "var(--border)" }}>
        {TABS.map(({ href, label }) => {
          const isActive = href === current || (href !== "/tracker" && pathname.startsWith(href));
          return (
            <Link
              key={href}
              href={href}
              className="px-4 py-2.5 text-sm font-medium -mb-px border-b-2 transition-colors"
              style={{
                borderColor: isActive ? "var(--accent)" : "transparent",
                color: isActive ? "var(--accent)" : "var(--text-secondary)",
              }}
            >
              {label}
            </Link>
          );
        })}
      </nav>
    </div>
  );
}
