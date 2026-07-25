import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // Export a fully static site (HTML/CSS/JS) into `out/` — upload to public_html
  // on Hostinger shared/Premium hosting. No Node server required.
  output: "export",
  // Static hosting can't run Next's image optimizer.
  images: { unoptimized: true },
  // Emit folder/index.html per route (e.g. /about/index.html) so clean URLs and
  // page refreshes work on LiteSpeed/Apache shared hosting.
  trailingSlash: true,
};

export default nextConfig;
