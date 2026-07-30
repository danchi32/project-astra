"use client";

/**
 * A bordered panel that scrolls inside itself instead of stretching the page.
 *
 * These lists grew as tall as their content, so the page scrolled and the panel's own
 * horizontal scrollbar sat at the very bottom of it — you had to scroll all the way down
 * past every row to reach the control that moves the columns sideways, and the column
 * headers had scrolled out of sight by the time you got there, so you could no longer tell
 * which column you were looking at.
 *
 * The panel now claims the leftover height of the viewport and owns both scrollbars, so
 * they are always where the content is. Requires the page root to be a flex column with a
 * definite height — see `pageShell`.
 */
export function ScrollPanel({
  children,
  footer,
  className = "",
}: {
  children: React.ReactNode;
  /** Pinned to the bottom of the panel — pagination and the like, which should stay put
   *  rather than scroll away with the rows they describe. */
  footer?: React.ReactNode;
  className?: string;
}) {
  return (
    // min-h-0 is load-bearing: a flex item defaults to min-height:auto, which refuses to
    // shrink below its content, so without it the panel grows tall again and the scrollbar
    // goes right back to the bottom of the page.
    <div
      className="flex-1 min-h-0 rounded-xl overflow-hidden flex flex-col"
      style={{ border: "1px solid var(--border)" }}
    >
      <div
        className={`flex-1 min-h-0 overflow-auto ${className}`}
        style={{ background: "var(--surface)" }}
      >
        {children}
      </div>
      {footer}
    </div>
  );
}

/** Root classes for a page whose main content is a ScrollPanel. */
export const pageShell = "flex flex-col gap-6 h-full min-h-0";

/**
 * Header cell for a table inside a ScrollPanel. The sticky offset lives on the cells rather
 * than the row because a positioned `thead`/`tr` drops its borders in a collapsed table —
 * hence the inset shadow instead of border-bottom, and an opaque background so rows don't
 * show through as they pass underneath.
 */
export const stickyHeadCell: React.CSSProperties = {
  position: "sticky",
  top: 0,
  zIndex: 10,
  background: "var(--surface)",
  boxShadow: "inset 0 -1px 0 var(--border)",
  color: "var(--text-secondary)",
};
