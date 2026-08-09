import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight, CalendarDays, Clock } from "lucide-react";
import { Container, Section, Badge, SectionHeading } from "@/components/ui";
import { getAllPosts } from "@/lib/blog";

export const metadata: Metadata = {
  title: "Blog — AI IT Automation, Self-Healing & Secure Offboarding",
  description:
    "Practical guides on AI-driven IT automation, self-healing endpoints, secure employee offboarding and reducing IT support tickets — from the Technomate team.",
  alternates: { canonical: "/blog/" },
};

function formatDate(iso: string): string {
  if (!iso) return "";
  return new Date(iso + "T00:00:00Z").toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}

export default function BlogIndexPage() {
  const posts = getAllPosts();

  return (
    <Section className="aurora grain relative -mt-16 pt-28 sm:pt-36">
      <Container>
        <div className="mx-auto max-w-2xl text-center">
          <Badge>Blog</Badge>
          <SectionHeading
            title="Insights on AI-driven IT operations"
            subtitle="Practical guides on IT automation, self-healing endpoints, secure offboarding and cutting support tickets."
          />
        </div>

        <div className="mx-auto mt-14 grid max-w-4xl gap-5 sm:grid-cols-2">
          {posts.map((post) => (
            <Link
              key={post.slug}
              href={`/blog/${post.slug}/`}
              className="group flex flex-col rounded-2xl border border-token bg-surface p-6 transition-all hover:-translate-y-0.5 hover:border-brand-500/50"
            >
              <div className="flex items-center gap-4 text-xs text-muted-token">
                <span className="inline-flex items-center gap-1.5">
                  <CalendarDays className="h-3.5 w-3.5" /> {formatDate(post.date)}
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <Clock className="h-3.5 w-3.5" /> {post.readingMinutes} min
                </span>
              </div>
              <h2 className="mt-3 text-lg font-bold leading-snug">
                {post.title}
              </h2>
              <p className="mt-2 flex-1 text-sm leading-relaxed text-secondary-token">
                {post.description}
              </p>
              <span className="mt-4 inline-flex items-center gap-1.5 text-sm font-semibold text-brand-500">
                Read article
                <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
              </span>
            </Link>
          ))}
        </div>
      </Container>
    </Section>
  );
}
