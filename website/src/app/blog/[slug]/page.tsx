import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft, ArrowRight, CalendarDays, Clock } from "lucide-react";
import { Container, Button } from "@/components/ui";
import { site, bookDemo } from "@/lib/site";
import { getAllSlugs, getPost } from "@/lib/blog";

export function generateStaticParams() {
  return getAllSlugs().map((slug) => ({ slug }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const post = await getPost(slug);
  if (!post) return {};
  return {
    title: post.title,
    description: post.description,
    keywords: post.keywords,
    alternates: { canonical: `/blog/${slug}/` },
    openGraph: {
      title: post.title,
      description: post.description,
      url: `/blog/${slug}/`,
      type: "article",
      publishedTime: post.date,
    },
  };
}

function formatDate(iso: string): string {
  if (!iso) return "";
  const d = new Date(iso + "T00:00:00Z");
  return d.toLocaleDateString("en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
    timeZone: "UTC",
  });
}

export default async function BlogPostPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const post = await getPost(slug);
  if (!post) notFound();

  const base = `https://${site.domain}`;
  const articleLd = {
    "@context": "https://schema.org",
    "@type": "BlogPosting",
    headline: post.title,
    description: post.description,
    datePublished: post.date,
    dateModified: post.date,
    author: { "@type": "Organization", name: post.author },
    publisher: { "@id": `${base}/#organization` },
    mainEntityOfPage: `${base}/blog/${slug}/`,
    keywords: post.keywords.join(", "),
  };

  return (
    <article className="pt-8 pb-24 sm:pt-12">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(articleLd) }}
      />
      <Container className="max-w-3xl">
        <Link
          href="/blog"
          className="inline-flex items-center gap-1.5 text-sm font-medium text-secondary-token hover:text-brand-500"
        >
          <ArrowLeft className="h-4 w-4" /> All articles
        </Link>

        <h1 className="mt-6 text-3xl font-bold tracking-tight sm:text-4xl">
          {post.title}
        </h1>

        <div className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-2 text-sm text-muted-token">
          <span className="inline-flex items-center gap-1.5">
            <CalendarDays className="h-4 w-4" /> {formatDate(post.date)}
          </span>
          <span className="inline-flex items-center gap-1.5">
            <Clock className="h-4 w-4" /> {post.readingMinutes} min read
          </span>
          <span>By {post.author}</span>
        </div>

        <div
          className="prose prose-neutral mt-10 max-w-none dark:prose-invert prose-headings:tracking-tight prose-a:font-medium prose-a:text-brand-600 prose-a:no-underline hover:prose-a:underline dark:prose-a:text-brand-400"
          dangerouslySetInnerHTML={{ __html: post.html }}
        />

        {/* End-of-article CTA */}
        <div className="mt-14 rounded-2xl border border-token bg-brand-600/[0.07] p-8 text-center">
          <h2 className="text-xl font-bold tracking-tight">
            See {site.product} in action
          </h2>
          <p className="mx-auto mt-2 max-w-lg text-sm text-secondary-token">
            {site.product} is the AI System Administrator that diagnoses and
            self-heals IT issues — with human approval where it matters.
          </p>
          <div className="mt-6 flex flex-wrap justify-center gap-3">
            <Button href={bookDemo.href} external={bookDemo.external}>
              Book a demo <ArrowRight className="h-4 w-4" />
            </Button>
            <Button href="/astra" variant="secondary">
              Explore {site.product}
            </Button>
          </div>
        </div>
      </Container>
    </article>
  );
}
