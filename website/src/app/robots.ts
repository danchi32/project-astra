import type { MetadataRoute } from "next";
import { site } from "@/lib/site";

// Generates /robots.txt at build time (static export compatible).
export const dynamic = "force-static";

export default function robots(): MetadataRoute.Robots {
  const base = `https://${site.domain}`;
  return {
    rules: [
      {
        userAgent: "*",
        allow: "/",
      },
    ],
    sitemap: `${base}/sitemap.xml`,
    host: base,
  };
}
