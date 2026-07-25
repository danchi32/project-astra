import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { comparisons, getComparison } from "@/lib/comparisons";
import { CompareContent } from "./CompareContent";

// Pre-render one static page per comparison (required for `output: export`).
export function generateStaticParams() {
  return comparisons.map((c) => ({ slug: c.slug }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
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
