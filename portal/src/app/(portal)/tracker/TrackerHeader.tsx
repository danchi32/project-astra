"use client";
import { Clock } from "lucide-react";

/** The shared heading for each Tracker section. Navigation lives in the sidebar (the Tracker
 *  nav expands to its sections), so a page just names itself. */
export function TrackerHeader({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="flex items-center gap-2">
      <div className="p-2 rounded-lg" style={{ background: "rgba(154,47,187,0.1)", color: "var(--accent)" }}>
        <Clock size={18} />
      </div>
      <div>
        <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>{title}</h1>
        {subtitle && <p className="text-sm mt-0.5" style={{ color: "var(--text-secondary)" }}>{subtitle}</p>}
      </div>
    </div>
  );
}
