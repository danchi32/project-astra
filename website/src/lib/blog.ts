import fs from "node:fs";
import path from "node:path";
import matter from "gray-matter";
import { marked } from "marked";

/**
 * Build-time blog loader. Articles are Markdown files in `content/blog/*.md`
 * with YAML frontmatter. Everything here runs at build time (static export),
 * so filesystem access is fine — nothing ships to the client.
 */

const BLOG_DIR = path.join(process.cwd(), "content", "blog");

/** A question and its answer. The answer is Markdown, so it may carry links. */
export type Faq = { q: string; a: string };

export type PostMeta = {
  slug: string;
  title: string;
  description: string;
  date: string; // ISO (YYYY-MM-DD)
  updated?: string; // ISO (YYYY-MM-DD)
  author: string;
  keywords: string[];
  readingMinutes: number;
  faq: Faq[];
};

export type Post = PostMeta & { html: string; faqHtml: { q: string; html: string }[] };

function readRaw(slug: string): { data: Record<string, unknown>; content: string } {
  const full = path.join(BLOG_DIR, `${slug}.md`);
  const file = fs.readFileSync(full, "utf8");
  return matter(file);
}

function estimateReadingMinutes(markdown: string): number {
  const words = markdown.trim().split(/\s+/).length;
  return Math.max(1, Math.round(words / 200));
}

function toMeta(slug: string, data: Record<string, unknown>, content: string): PostMeta {
  return {
    slug,
    title: String(data.title ?? slug),
    description: String(data.description ?? ""),
    date: String(data.date ?? ""),
    updated: data.updated ? String(data.updated) : undefined,
    author: String(data.author ?? "Technomate IT-Solution"),
    keywords: Array.isArray(data.keywords) ? (data.keywords as string[]) : [],
    readingMinutes: estimateReadingMinutes(content),
    faq: Array.isArray(data.faq)
      ? (data.faq as Record<string, unknown>[]).map((f) => ({ q: String(f.q), a: String(f.a) }))
      : [],
  };
}

export function getAllSlugs(): string[] {
  if (!fs.existsSync(BLOG_DIR)) return [];
  return fs
    .readdirSync(BLOG_DIR)
    .filter((f) => f.endsWith(".md"))
    .map((f) => f.replace(/\.md$/, ""));
}

/** All posts, newest first (for the blog index). */
export function getAllPosts(): PostMeta[] {
  return getAllSlugs()
    .map((slug) => {
      const { data, content } = readRaw(slug);
      return toMeta(slug, data, content);
    })
    .sort((a, b) => (a.date < b.date ? 1 : -1));
}

/** A single post with rendered HTML body. */
export async function getPost(slug: string): Promise<Post | null> {
  try {
    const { data, content } = readRaw(slug);
    const html = await marked.parse(content);
    const meta = toMeta(slug, data, content);
    const faqHtml = await Promise.all(
      meta.faq.map(async (f) => ({ q: f.q, html: await marked.parseInline(f.a) })),
    );
    return { ...meta, html, faqHtml };
  } catch {
    return null;
  }
}
