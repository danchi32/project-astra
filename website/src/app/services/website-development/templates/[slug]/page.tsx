import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { getTemplate, siteTemplates } from "@/lib/services";
import { TemplatePreview } from "./TemplatePreview";

// One static page per template (required for `output: export`).
export function generateStaticParams() {
  return siteTemplates.map((t) => ({ slug: t.slug }));
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params;
  const t = getTemplate(slug);
  if (!t) return {};
  return {
    title: `${t.name} — ${t.industry} website template`,
    description: `Live preview of the ${t.name} ${t.industry.toLowerCase()} website template by Technomate IT-Solution. ${t.desc}`,
    alternates: { canonical: `/services/website-development/templates/${t.slug}/` },
  };
}

export default async function TemplatePage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  if (!getTemplate(slug)) notFound();
  return <TemplatePreview slug={slug} />;
}
