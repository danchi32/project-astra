import { type LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface StatCardProps {
  title: string;
  value: string | number;
  sub?: string;
  icon: LucideIcon;
  variant?: "default" | "success" | "warning" | "danger";
}

const variantStyles = {
  default: "text-brand-500 bg-brand-500/10",
  success: "text-emerald-500 bg-emerald-500/10",
  warning: "text-amber-500 bg-amber-500/10",
  danger: "text-red-500 bg-red-500/10",
} as const;

export function StatCard({ title, value, sub, icon: Icon, variant = "default" }: StatCardProps) {
  return (
    <div
      className="rounded-xl p-5 flex items-start gap-4"
      style={{ background: "var(--surface)", border: "1px solid var(--border)" }}
    >
      <div className={cn("p-2.5 rounded-lg shrink-0", variantStyles[variant])}>
        <Icon size={20} />
      </div>
      <div className="min-w-0">
        <p className="text-xs font-medium uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>
          {title}
        </p>
        <p className="mt-0.5 text-2xl font-bold tabular-nums" style={{ color: "var(--text-primary)" }}>
          {value}
        </p>
        {sub && (
          <p className="text-xs mt-0.5" style={{ color: "var(--text-secondary)" }}>{sub}</p>
        )}
      </div>
    </div>
  );
}
