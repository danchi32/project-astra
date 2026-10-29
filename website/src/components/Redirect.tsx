/**
 * A moved page, for a static export that has no server to answer with a 301.
 *
 * The product was renamed ASTRA → SAVIO and its URLs moved with it (/astra/ → /savio/,
 * /compare/astra-vs-* → /compare/savio-vs-*). Search results, blog posts on other sites and
 * bookmarks still point at the old ones, so each old path renders this: an instant
 * meta-refresh (React 19 hoists the <meta> into <head>), plus a plain link for anything that
 * ignores it. Pair it with `robots: { index: false }` and a canonical to the new URL in the
 * page's metadata so the old address drops out of the index instead of competing.
 *
 * ponytail: a real 301 in the host's .htaccess is the upgrade path, if Hostinger's config
 * ever moves into this repo.
 */
export function Redirect({ to }: { to: string }) {
  return (
    <>
      <meta httpEquiv="refresh" content={`0; url=${to}`} />
      <div className="mx-auto max-w-xl px-6 py-32 text-center">
        <p className="text-secondary-token">
          This page has moved to <a className="font-semibold text-brand-500 underline" href={to}>{to}</a>.
        </p>
      </div>
    </>
  );
}
