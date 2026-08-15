"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { Bell, LifeBuoy, Settings, LogOut, Monitor, Sun, Moon } from "lucide-react";
import { getMe, logout } from "@/lib/api/auth";
import { getUnreadCount } from "@/lib/api/notifications";
import { getTheme, setTheme, type Theme } from "@/lib/theme";

/** Two initials for the avatar: from the name if there is one, otherwise the email.
 *  Never empty — a blank avatar reads as a broken image rather than a signed-in user. */
function initials(name?: string, email?: string): string {
  const source = (name || "").trim();
  if (source) {
    const parts = source.split(/\s+/);
    const first = parts[0][0] ?? "";
    const last = parts.length > 1 ? parts[parts.length - 1][0] ?? "" : "";
    return (first + last).toUpperCase() || source[0].toUpperCase();
  }
  return (email || "?").trim()[0]?.toUpperCase() ?? "?";
}

/** A round icon button, so every item in the strip is the same shape and hit-area. */
function IconButton({
  label, badge, href, onClick, children,
}: {
  label: string;
  badge?: number;
  href?: string;
  onClick?: () => void;
  children: React.ReactNode;
}) {
  const inner = (
    <span className="relative inline-flex items-center justify-center w-9 h-9 rounded-full transition-colors hover:bg-[var(--bg)]"
      style={{ color: "var(--text-secondary)" }}>
      {children}
      {!!badge && (
        <span className="absolute -top-0.5 -right-0.5 min-w-4 h-4 px-1 flex items-center justify-center text-[10px] font-semibold rounded-full leading-none"
          style={{ background: "#ef4444", color: "white" }}>
          {badge > 99 ? "99+" : badge}
        </span>
      )}
    </span>
  );
  return href ? (
    <Link href={href} aria-label={label} title={label}>{inner}</Link>
  ) : (
    <button onClick={onClick} aria-label={label} title={label}>{inner}</button>
  );
}

/** The global top strip: notifications, help, and the profile menu — the things that used
 *  to sit at the foot of the sidebar, where they were easy to miss. Rendered once by the
 *  layout, above every page. */
export function Topbar() {
  const router = useRouter();
  const { data: me } = useQuery({ queryKey: ["me"], queryFn: getMe });
  const { data: unread } = useQuery({
    queryKey: ["unread-notifications"],
    queryFn: getUnreadCount,
    refetchInterval: 30_000,
  });

  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  // Close the profile menu on an outside click or Escape — a menu that only closes by
  // reselecting the avatar traps the pointer and feels broken.
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  // Theme is read once on mount rather than during render: getTheme touches localStorage,
  // which does not exist while the server renders this component.
  const [theme, setThemeState] = useState<Theme>("system");
  useEffect(() => setThemeState(getTheme()), []);
  const chooseTheme = (t: Theme) => { setTheme(t); setThemeState(t); };

  async function handleLogout() {
    await logout();
    router.push("/login");
  }

  const themes: { value: Theme; icon: typeof Sun; label: string }[] = [
    { value: "light", icon: Sun, label: "Light" },
    { value: "dark", icon: Moon, label: "Dark" },
    { value: "system", icon: Monitor, label: "System" },
  ];

  return (
    <header
      className="shrink-0 flex items-center justify-end gap-1 px-4 h-14"
      style={{ background: "var(--surface)", borderBottom: "1px solid var(--border)" }}
    >
      <IconButton label="Notifications" href="/notifications" badge={unread}>
        <Bell size={18} />
      </IconButton>
      <IconButton label="Help & Support" href="/help">
        <LifeBuoy size={18} />
      </IconButton>

      {/* Profile menu */}
      <div className="relative ml-1" ref={menuRef}>
        <button
          onClick={() => setOpen((v) => !v)}
          aria-label="Account menu"
          aria-expanded={open}
          className="w-9 h-9 rounded-full flex items-center justify-center text-xs font-semibold text-white"
          style={{ background: "linear-gradient(135deg, var(--accent), #6d28d9)" }}
        >
          {initials(me?.full_name, me?.email)}
        </button>

        {open && (
          <div
            className="absolute right-0 mt-2 w-60 rounded-xl overflow-hidden z-50 shadow-lg"
            style={{ background: "var(--surface)", border: "1px solid var(--border)" }}
          >
            <div className="px-4 py-3" style={{ borderBottom: "1px solid var(--border)" }}>
              <div className="text-sm font-semibold truncate" style={{ color: "var(--text-primary)" }}>
                {me?.full_name || "Signed in"}
              </div>
              <div className="text-xs truncate" style={{ color: "var(--text-secondary)" }}>
                {me?.email}
              </div>
            </div>

            <div className="py-1">
              <Link
                href="/settings"
                onClick={() => setOpen(false)}
                className="flex items-center gap-2.5 px-4 py-2 text-sm transition-colors hover:bg-[var(--bg)]"
                style={{ color: "var(--text-primary)" }}
              >
                <Settings size={15} /> Settings
              </Link>
            </div>

            <div className="px-4 py-2" style={{ borderTop: "1px solid var(--border)" }}>
              <div className="text-[11px] uppercase tracking-wide mb-1.5" style={{ color: "var(--text-secondary)" }}>
                Theme
              </div>
              <div className="flex gap-1">
                {themes.map(({ value, icon: Icon, label }) => (
                  <button
                    key={value}
                    onClick={() => chooseTheme(value)}
                    title={label}
                    className="flex-1 flex items-center justify-center gap-1 py-1.5 rounded-md text-xs transition-colors"
                    style={{
                      background: theme === value ? "rgba(154,47,187,0.12)" : "transparent",
                      color: theme === value ? "var(--accent)" : "var(--text-secondary)",
                      border: "1px solid " + (theme === value ? "var(--accent)" : "var(--border)"),
                    }}
                  >
                    <Icon size={13} /> {label}
                  </button>
                ))}
              </div>
            </div>

            <div className="py-1" style={{ borderTop: "1px solid var(--border)" }}>
              <button
                onClick={handleLogout}
                className="flex items-center gap-2.5 w-full px-4 py-2 text-sm transition-colors hover:bg-red-500/10 hover:text-red-500"
                style={{ color: "var(--text-secondary)" }}
              >
                <LogOut size={15} /> Sign out
              </button>
            </div>
          </div>
        )}
      </div>
    </header>
  );
}
