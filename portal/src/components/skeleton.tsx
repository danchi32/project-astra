import type { CSSProperties } from "react";
import { cn } from "@/lib/utils";

/** Base pulsing placeholder block. Compose into card/table skeletons. */
export function SkeletonBlock({
  className,
  style,
}: {
  className?: string;
  style?: CSSProperties;
}) {
  return (
    <div
      className={cn("animate-pulse rounded-md", className)}
      style={{ background: "var(--border)", ...style }}
    />
  );
}

/** Placeholder matching StatCard's shape (icon chip + label + value). */
export function SkeletonStatCard() {
  return (
    <div
      className="rounded-xl p-5 flex items-start gap-4"
      style={{ background: "var(--surface)", border: "1px solid var(--border)" }}
    >
      <SkeletonBlock className="w-11 h-11 shrink-0" />
      <div className="min-w-0 flex-1 space-y-2">
        <SkeletonBlock className="h-3 w-2/3" />
        <SkeletonBlock className="h-6 w-1/2" />
      </div>
    </div>
  );
}

/** Placeholder matching a generic bordered card with a title bar and body. */
export function SkeletonPanel({ lines = 3, height }: { lines?: number; height?: number }) {
  return (
    <div
      className="rounded-xl p-5 space-y-3"
      style={{ background: "var(--surface)", border: "1px solid var(--border)", minHeight: height }}
    >
      <SkeletonBlock className="h-3 w-1/3" />
      {Array.from({ length: lines }).map((_, i) => (
        <SkeletonBlock key={i} className="h-4 w-full" />
      ))}
    </div>
  );
}

/** Placeholder matching an InsightCard hero card (title, big metric, breakdown rows, button bar). */
export function SkeletonInsightCard() {
  return (
    <div
      className="rounded-2xl p-6 space-y-4"
      style={{ background: "var(--surface)", border: "1px solid var(--border)" }}
    >
      <div className="space-y-2">
        <SkeletonBlock className="h-3 w-1/3" />
        <SkeletonBlock className="h-2.5 w-1/2" />
      </div>
      <SkeletonBlock className="h-8 w-1/4" />
      <div className="space-y-2.5">
        <SkeletonBlock className="h-2.5 w-full" />
        <SkeletonBlock className="h-2.5 w-full" />
        <SkeletonBlock className="h-2.5 w-3/4" />
      </div>
      <div className="pt-2 flex gap-2">
        <SkeletonBlock className="h-8 w-24" />
        <SkeletonBlock className="h-8 w-24" />
      </div>
    </div>
  );
}

export function SkeletonTableRow({ cols }: { cols: number }) {
  return (
    <tr style={{ borderBottom: "1px solid var(--border)" }}>
      {Array.from({ length: cols }).map((_, i) => (
        <td key={i} className="px-4 py-3">
          <SkeletonBlock className="h-4 w-full max-w-[140px]" />
        </td>
      ))}
    </tr>
  );
}

/** Placeholder matching Gauge/donut circular components. */
export function SkeletonCircle({ size = 96 }: { size?: number }) {
  return (
    <div
      className="flex flex-col items-center gap-2 p-5 rounded-xl"
      style={{ background: "var(--surface)", border: "1px solid var(--border)" }}
    >
      <SkeletonBlock className="rounded-full" style={{ width: size, height: size }} />
    </div>
  );
}
