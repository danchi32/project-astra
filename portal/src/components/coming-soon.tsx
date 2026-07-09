import type { LucideIcon } from "lucide-react";

export function ComingSoon({
  icon: Icon,
  title,
  description,
  phase,
}: {
  icon: LucideIcon;
  title: string;
  description: string;
  phase: string;
}) {
  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <div className="p-2 rounded-lg" style={{ background: "rgba(37,99,235,0.1)", color: "var(--accent)" }}>
          <Icon size={18} />
        </div>
        <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>{title}</h1>
      </div>

      <div className="rounded-xl p-12 flex flex-col items-center text-center"
        style={{ background: "var(--surface)", border: "1px dashed var(--border)" }}>
        <div className="p-4 rounded-2xl mb-4" style={{ background: "rgba(37,99,235,0.08)", color: "var(--accent)" }}>
          <Icon size={32} />
        </div>
        <p className="text-base font-medium" style={{ color: "var(--text-primary)" }}>{description}</p>
        <span className="mt-3 text-xs font-medium px-3 py-1 rounded-full"
          style={{ background: "rgba(245,158,11,0.12)", color: "#f59e0b" }}>
          {phase}
        </span>
      </div>
    </div>
  );
}
