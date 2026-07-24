"use client";
import { useState, useRef, useEffect } from "react";
import { ChevronDown } from "lucide-react";

export interface FilterOption {
  value: string;
  label: string;
}

export function MultiSelectFilter({
  label,
  options,
  selected,
  onChange,
}: {
  label: string;
  options: FilterOption[];
  selected: string[];
  onChange: (values: string[]) => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  function toggle(value: string) {
    onChange(selected.includes(value) ? selected.filter((v) => v !== value) : [...selected, value]);
  }

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium whitespace-nowrap"
        style={{
          background: selected.length ? "rgba(154,47,187,0.1)" : "var(--bg)",
          border: "1px solid var(--border)",
          color: selected.length ? "var(--accent)" : "var(--text-primary)",
        }}
      >
        {label}{selected.length ? ` (${selected.length})` : ""}
        <ChevronDown size={14} />
      </button>
      {open && (
        <div
          className="absolute z-20 mt-1 w-56 max-h-64 overflow-y-auto rounded-lg p-1.5 shadow-lg"
          style={{ background: "var(--surface)", border: "1px solid var(--border)" }}
        >
          {options.length === 0 && (
            <p className="px-2 py-1.5 text-xs" style={{ color: "var(--text-secondary)" }}>No options</p>
          )}
          {options.map((opt) => (
            <label
              key={opt.value}
              className="flex items-center gap-2 px-2 py-1.5 rounded-md text-sm cursor-pointer hover:bg-brand-500/5"
              style={{ color: "var(--text-primary)" }}
            >
              <input
                type="checkbox"
                checked={selected.includes(opt.value)}
                onChange={() => toggle(opt.value)}
              />
              <span className="capitalize truncate">{opt.label}</span>
            </label>
          ))}
        </div>
      )}
    </div>
  );
}
