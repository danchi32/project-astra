import type { MetadataRoute } from "next";
import { site } from "@/lib/site";

// Generates /manifest.webmanifest at build time (static export compatible).
export const dynamic = "force-static";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: `${site.company} — ${site.product} AI`,
    short_name: site.brandShort,
    description:
      "Managed IT services, hardware, and Astra — the AI System Administrator that automates IT support.",
    start_url: "/",
    display: "standalone",
    background_color: "#0b1120",
    theme_color: "#b246d4",
    icons: [
      { src: "/icon.svg", sizes: "any", type: "image/svg+xml" },
      { src: "/logo.png", sizes: "512x512", type: "image/png" },
    ],
  };
}
