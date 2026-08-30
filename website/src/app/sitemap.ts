import type { MetadataRoute } from "next";
import { legalNav, site } from "@/lib/site";
import { comparisons } from "@/lib/comparisons";
import { getAllPosts } from "@/lib/blog";

// Generates /sitemap.xml at build time (static export compatible).
export const dynamic = "force-static";

export default function sitemap(): MetadataRoute.Sitemap {
  const base = `https://${site.domain}`;
  const routes: { path: string; priority: number; changeFrequency: MetadataRoute.Sitemap[number]["changeFrequency"] }[] = [
    { path: "/", priority: 1.0, changeFrequency: "weekly" },
    { path: "/astra/", priority: 0.9, changeFrequency: "weekly" },
    { path: "/ai-it-support-india/", priority: 0.9, changeFrequency: "monthly" },
    { path: "/pricing/", priority: 0.8, changeFrequency: "monthly" },
    { path: "/compare/", priority: 0.7, changeFrequency: "monthly" },
    { path: "/blog/", priority: 0.7, changeFrequency: "weekly" },
    { path: "/resources/offboarding-checklist/", priority: 0.7, changeFrequency: "monthly" },
    { path: "/security/", priority: 0.8, changeFrequency: "monthly" },
    { path: "/about/", priority: 0.6, changeFrequency: "monthly" },
    { path: "/contact/", priority: 0.6, changeFrequency: "monthly" },
    // Policy pages. Low priority but deliberately indexed — buyers' security reviewers
    // and the payment rails both look for these at a public URL.
    ...legalNav.map((l) => ({
      path: `${l.href}/`,
      priority: 0.3,
      changeFrequency: "yearly" as const,
    })),
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
