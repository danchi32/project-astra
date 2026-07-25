import type { MetadataRoute } from "next";
import { site } from "@/lib/site";
import { comparisons } from "@/lib/comparisons";
import { getAllPosts } from "@/lib/blog";

// Generates /sitemap.xml at build time (static export compatible).
export const dynamic = "force-static";

export default function sitemap(): MetadataRoute.Sitemap {
  const base = `https://${site.domain}`;
  const routes: { path: string; priority: number; changeFrequency: MetadataRoute.Sitemap[number]["changeFrequency"] }[] = [
    { path: "/", priority: 1.0, changeFrequency: "weekly" },
    { path: "/astra/", priority: 0.9, changeFrequency: "weekly" },
    { path: "/pricing/", priority: 0.8, changeFrequency: "monthly" },
    { path: "/compare/", priority: 0.7, changeFrequency: "monthly" },
    { path: "/blog/", priority: 0.7, changeFrequency: "weekly" },
    { path: "/about/", priority: 0.6, changeFrequency: "monthly" },
    { path: "/contact/", priority: 0.6, changeFrequency: "monthly" },
    // One entry per comparison landing page.
    ...comparisons.map((c) => ({
      path: `/compare/${c.slug}/`,
      priority: 0.8,
      changeFrequency: "monthly" as const,
    })),
    // One entry per blog post.
    ...getAllPosts().map((p) => ({
      path: `/blog/${p.slug}/`,
      priority: 0.7,
      changeFrequency: "monthly" as const,
    })),
  ];

  return routes.map((r) => ({
    url: `${base}${r.path}`,
    changeFrequency: r.changeFrequency,
    priority: r.priority,
  }));
}
