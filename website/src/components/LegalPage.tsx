import type { ReactNode } from "react";
import { AlertTriangle } from "lucide-react";
import { Container, Section } from "@/components/ui";
import { site } from "@/lib/site";

/**
 * Shared shell for every policy page.
 *
 * Two things it guarantees, which is the whole reason it exists rather than each page
 * repeating itself: the statutory entity block appears identically on all of them, and
 * a page that has not yet been through legal review says so on its face.
 */
export function LegalPage({
  title,
  effective,
  intro,
  reviewed = false,
  children,
}: {
  title: string;
  /** ISO date this version takes effect. */
  effective: string;
  intro?: ReactNode;
  /** Flip to true once counsel has signed the text off. Until then a banner renders. */
  reviewed?: boolean;
  children: ReactNode;
}) {
  const { legal } = site;
  return (
    <Section className="pt-28">
      <Container>
        <div className="mx-auto max-w-3xl">
          <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">
            {title}
          </h1>
          <p className="mt-3 text-sm text-muted-token">
            {legal.displayName} &middot; Effective {effective}
          </p>

          {!reviewed && (
            /* Deliberately loud and deliberately not dismissible. These documents were
               drafted from what the software actually does; the clauses that allocate
               risk are a lawyer's to write. Set `reviewed` once that has happened. */
            <div className="mt-6 flex gap-3 rounded-xl border border-amber-500/40 bg-amber-500/10 p-4 text-sm">
              <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-amber-500" />
              <div className="text-secondary-token">
                <strong className="text-primary-token">
                  Draft — pending legal review.
                </strong>{" "}
                This document has not yet been reviewed by counsel and must not be
                relied upon as final. Sections marked{" "}
                <em>“to be completed by counsel”</em> are intentionally unfinished.
              </div>
            </div>
          )}

          {intro && (
            <div className="mt-8 text-base leading-relaxed text-secondary-token">
              {intro}
            </div>
          )}

          <div className="prose prose-slate mt-10 max-w-none dark:prose-invert prose-headings:scroll-mt-24 prose-a:text-brand-600 prose-headings:font-semibold">
            {children}
          </div>

        </div>
      </Container>
    </Section>
  );
}

/** Marks a clause that is deliberately unfinished, so it cannot be mistaken for text. */
export function CounselTodo({ children }: { children: ReactNode }) {
  return (
    <p className="rounded-lg border border-dashed border-amber-500/50 bg-amber-500/5 px-4 py-3 text-sm not-prose text-secondary-token">
      <strong className="text-amber-600 dark:text-amber-400">
        To be completed by counsel:
      </strong>{" "}
      {children}
    </p>
  );
}
