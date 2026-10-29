import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { comparisons, getComparison } from "@/lib/comparisons";
import { Redirect } from "@/components/Redirect";
import { CompareContent } from "./CompareContent";

// Pages from before the ASTRA → SAVIO rename, kept as redirects so old links still land.
const LEGACY_PREFIX = "astra-vs-";
const renamed = (slug: string) => "savio-vs-" + slug.slice(LEGACY_PREFIX.length);

// Pre-render one static page per comparison (required for `output: export`), plus a
// redirect at each comparison's pre-rename address.
export function generateStaticParams() {
  return comparisons.flatMap((c) => [
    { slug: c.slug },
    { slug: LEGACY_PREFIX + c.slug.replace(/^savio-vs-/, "") },
  ]);
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  if (slug.startsWith(LEGACY_PREFIX)) {
    return {
      robots: { index: false, follow: true },
      alternates: { canonical: `/compare/${renamed(slug)}/` },
    };
  }
  const data = getComparison(slug);
  if (!data) return {};
  return {
    title: data.title,
    description: data.description,
    alternates: { canonical: `/compare/${data.slug}/` },
    openGraph: {
      title: data.title,
      description: data.description,
      url: `/compare/${data.slug}/`,
      type: "article",
    },
  };
}

export default async function ComparePage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  if (slug.startsWith(LEGACY_PREFIX)) return <Redirect to={`/compare/${renamed(slug)}/`} />;
  const data = getComparison(slug);
  if (!data) notFound();

  // FAQPage structured data → eligible for rich results in search.
  const faqLd = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: data.faqs.map((f) => ({
      "@type": "Question",
      name: f.q,
      acceptedAnswer: { "@type": "Answer", text: f.a },
    })),
  };

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(faqLd) }}
      />
      <CompareContent data={data} />
    </>
  );
}
