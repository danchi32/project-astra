import type { MetadataRoute } from "next";
import { site } from "@/lib/site";

// Generates /manifest.webmanifest at build time (static export compatible).
export const dynamic = "force-static";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: `${site.company} — ${site.product} AI`,
    short_name: site.brandShort,
    description:
      "Managed IT services, hardware, and SAVIO — the AI System Administrator that automates IT support.",
    start_url: "/",
    display: "standalone",
    background_color: "#0b1120",
    theme_color: "#2563eb",
    icons: [
      { src: "/icon-192.png", sizes: "192x192", type: "image/png" },
      { src: "/icon-512.png", sizes: "512x512", type: "image/png" },
    ],
  };
}
