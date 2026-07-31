"use client";
import { ChevronLeft, ChevronRight } from "lucide-react";
import type { Page } from "@/lib/api/types";

/**
 * The footer for a paginated list, sized to sit in a ScrollPanel's footer slot.
 *
 * Shows the range and the total rather than just the page number: "Page 2 of 40" tells you
 * where you are but not how much there is, and the total is usually the number someone came
 * to the screen for.
 */
export function Pagination<T>({
  page,
  onPage,
  data,
  noun = "row",
  plural,
  busy = false,
}: {
  page: number;
  onPage: (next: number) => void;
  data: Page<T> | undefined;
  noun?: string;
  /** Given explicitly where "+s" would be wrong — "entry" is the one that catches people. */
  plural?: string;
  busy?: boolean;
}) {
  // Rendered even for a single page: the count is worth showing, and a footer that appears
  // and disappears as you filter makes the list jump under the cursor.
  if (!data || data.total === 0) return null;

  const from = (data.page - 1) * data.page_size + 1;
  const to = Math.min(data.page * data.page_size, data.total);

  return (
    <div
      className="flex items-center justify-between gap-3 px-4 py-3 flex-wrap"
      style={{ borderTop: "1px solid var(--border)", background: "var(--surface)" }}
    >
      <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
        Showing {from}–{to} of {data.total}{" "}
        {data.total === 1 ? noun : plural ?? `${noun}s`}
        {busy ? " · updating…" : ""}
      </p>
      {data.pages > 1 && (
        <div className="flex items-center gap-2">
          <button
            onClick={() => onPage(Math.max(1, page - 1))}
            disabled={page <= 1}
            className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-sm font-medium disabled:opacity-40"
            style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
          >
            <ChevronLeft size={15} /> Prev
          </button>
          <span className="text-xs" style={{ color: "var(--text-secondary)" }}>
            Page {data.page} of {data.pages}
          </span>
          <button
            onClick={() => onPage(Math.min(data.pages, page + 1))}
            disabled={page >= data.pages}
            className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-sm font-medium disabled:opacity-40"
            style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
          >
            Next <ChevronRight size={15} />
          </button>
        </div>
      )}
    </div>
  );
}
