"use client";
import { useEffect, useRef, useState } from "react";
import { ChevronDown, Search, Check } from "lucide-react";

export interface SelectOption {
  value: string;
  label: string;
  sublabel?: string;
  keywords?: string;  // extra text to match on (e.g. serial number, email)
}

/** A single-select dropdown with a built-in search box. Matches on label + sublabel +
 *  keywords, so a device can be found by hostname OR serial number, a user by name OR email. */
export function SearchableSelect({
  value,
  onChange,
  options,
  placeholder = "Select…",
  searchPlaceholder = "Search…",
}: {
  value: string;
  onChange: (value: string) => void;
  options: SelectOption[];
  placeholder?: string;
  searchPlaceholder?: string;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  const selected = options.find((o) => o.value === value);
  const q = query.trim().toLowerCase();
  const filtered = q
    ? options.filter((o) =>
        `${o.label} ${o.sublabel ?? ""} ${o.keywords ?? ""}`.toLowerCase().includes(q))
    : options;

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => { setOpen((v) => !v); setQuery(""); }}
        className="w-full mt-1 px-3 py-2 rounded-lg text-sm outline-none flex items-center justify-between gap-2 text-left"
        style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
      >
        <span className="truncate" style={{ opacity: selected ? 1 : 0.6 }}>
          {selected ? selected.label : placeholder}
        </span>
        <ChevronDown size={15} style={{ color: "var(--text-secondary)", flexShrink: 0 }} />
      </button>

      {open && (
        <div
          className="absolute z-50 mt-1 w-full rounded-lg overflow-hidden shadow-lg"
          style={{ background: "var(--surface)", border: "1px solid var(--border)" }}
        >
          <div className="p-2" style={{ borderBottom: "1px solid var(--border)" }}>
            <div className="relative">
              <Search size={13} className="absolute left-2 top-1/2 -translate-y-1/2" style={{ color: "var(--text-secondary)" }} />
              <input
                autoFocus
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder={searchPlaceholder}
                className="w-full pl-7 pr-2 py-1.5 rounded-md text-sm outline-none"
                style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
              />
            </div>
          </div>
          <div className="max-h-56 overflow-y-auto py-1">
            {filtered.length === 0 && (
              <div className="px-3 py-3 text-sm text-center" style={{ color: "var(--text-secondary)" }}>No matches</div>
            )}
            {filtered.map((o) => (
              <button
                key={o.value || "__none"}
                type="button"
                onClick={() => { onChange(o.value); setOpen(false); }}
                className="w-full px-3 py-2 text-left flex items-center gap-2 hover:bg-blue-500/10"
                style={{ color: "var(--text-primary)" }}
              >
                <span className="flex-1 min-w-0">
                  <span className="block text-sm truncate">{o.label}</span>
                  {o.sublabel && (
                    <span className="block text-xs truncate" style={{ color: "var(--text-secondary)" }}>{o.sublabel}</span>
                  )}
                </span>
                {o.value === value && <Check size={14} style={{ color: "var(--accent)", flexShrink: 0 }} />}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
