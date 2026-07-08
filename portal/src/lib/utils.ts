import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** Format megabytes as GB for display, e.g. 16065 -> "16 GB". */
export function formatRam(mb: number | null): string {
  if (mb == null || mb <= 0) return "—";
  return `${Math.round(mb / 1024)} GB`;
}

/** Format a GB storage figure, e.g. 476.9 -> "477 GB" or "1.0 TB". */
export function formatStorage(gb: number | null): string {
  if (gb == null || gb <= 0) return "—";
  if (gb >= 1024) return `${(gb / 1024).toFixed(1)} TB`;
  return `${Math.round(gb)} GB`;
}
