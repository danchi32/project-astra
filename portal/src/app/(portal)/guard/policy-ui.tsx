"use client";
import type { ReactNode } from "react";

// The browser-policy pages' building blocks: one look for every setting, so sections line up.
// Colours come from the theme's variables only (light and dark).

export const tint = (v: string, pct = 12) => `color-mix(in srgb, ${v} ${pct}%, transparent)`;
export const muted = { color: "var(--text-secondary)" };
export const field = { background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" };

/** A titled card holding a section's settings, one per row. */
export function Card({ title, description, action, children }: {
  title: string; description?: ReactNode; action?: ReactNode; children: ReactNode;
}) {
  return (
    <section className="rounded-xl" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
      <header className="flex flex-wrap items-start justify-between gap-3 px-5 py-4" style={{ borderBottom: "1px solid var(--border)" }}>
        <div className="min-w-0">
          <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>{title}</h3>
          {description && <p className="text-xs mt-0.5 max-w-2xl" style={muted}>{description}</p>}
        </div>
        {action}
      </header>
      <div className="divide-y" style={{ borderColor: "var(--border)" }}>{children}</div>
    </section>
  );
}

/** One setting: what it is on the left, its control on the right (or below, for wide ones). */
export function Setting({ title, help, children, wide = false }: {
  title: ReactNode; help?: ReactNode; children: ReactNode; wide?: boolean;
}) {
  return (
    <div className={`px-5 py-4 gap-3 ${wide ? "space-y-3" : "flex flex-col sm:flex-row sm:items-start sm:justify-between"}`}
      style={{ borderColor: "var(--border)" }}>
      <div className="min-w-0 sm:max-w-xl">
        <div className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>{title}</div>
        {help && <div className="text-xs mt-0.5" style={muted}>{help}</div>}
      </div>
      <div className={wide ? "" : "shrink-0"}>{children}</div>
    </div>
  );
}

/** An on/off switch. */
export function Toggle({ checked, onChange, disabled, label }: {
  checked: boolean; onChange: (v: boolean) => void; disabled?: boolean; label: string;
}) {
  return (
    <button type="button" role="switch" aria-checked={checked} aria-label={label} disabled={disabled}
      onClick={() => onChange(!checked)}
      className="relative inline-flex h-6 w-11 items-center rounded-full transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
      style={{ background: checked ? "var(--accent)" : "var(--border)" }}>
      <span className="inline-block h-5 w-5 rounded-full shadow transition-transform"
        style={{ background: "var(--surface)", transform: checked ? "translateX(22px)" : "translateX(2px)" }} />
    </button>
  );
}

/** A few mutually exclusive choices side by side, e.g. No change / Allow / Block. */
export function Choice<T extends string>({ value, options, onChange, disabled, label }: {
  value: T; options: readonly { value: T; label: string; tone?: "good" | "bad" }[]; onChange: (v: T) => void;
  disabled?: boolean; label: string;
}) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex rounded-lg p-0.5 gap-0.5" style={{ background: "var(--bg)", border: "1px solid var(--border)" }}>
      {options.map((o) => {
        const on = o.value === value;
        const colour = o.tone === "good" ? "var(--health-good)" : o.tone === "bad" ? "var(--health-bad)" : "var(--accent)";
        return (
          <button key={o.value} type="button" role="radio" aria-checked={on} disabled={disabled} onClick={() => onChange(o.value)}
            className="px-3 py-1 rounded-md text-xs font-medium whitespace-nowrap disabled:cursor-not-allowed"
            style={on ? { background: tint(colour, 16), color: colour } : { color: "var(--text-secondary)" }}>
            {o.label}
          </button>
        );
      })}
    </div>
  );
}

/** A small label: a team, a user, a status. */
export function Chip({ children, tone = "neutral", onRemove }: {
  children: ReactNode; tone?: "neutral" | "accent" | "good" | "warn" | "bad"; onRemove?: () => void;
}) {
  const colour = { neutral: "var(--text-secondary)", accent: "var(--accent)", good: "var(--health-good)",
                   warn: "var(--health-warn)", bad: "var(--health-bad)" }[tone];
  return (
    <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap"
      style={{ background: tint(colour), color: colour }}>
      {children}
      {onRemove && (
        <button type="button" onClick={onRemove} aria-label="Remove" className="leading-none opacity-70 hover:opacity-100">×</button>
      )}
    </span>
  );
}

/** A list typed one per line. */
export function Lines({ value, onChange, disabled, rows = 4, placeholder }: {
  value: string; onChange: (v: string) => void; disabled?: boolean; rows?: number; placeholder?: string;
}) {
  return (
    <textarea rows={rows} disabled={disabled} value={value} placeholder={placeholder} onChange={(e) => onChange(e.target.value)}
      className="w-full px-3 py-2 rounded-lg text-sm outline-none font-mono" style={field} />
  );
}

export const button = {
  primary: { background: "var(--accent)", color: "#fff" },
  plain: { border: "1px solid var(--border)", color: "var(--text-primary)", background: "var(--surface)" },
  danger: { border: "1px solid var(--border)", color: "var(--health-bad)", background: "var(--surface)" },
};
