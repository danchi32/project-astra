import type { Metadata } from "next";
import "./globals.css";
import { Navbar } from "@/components/Navbar";
import { Footer } from "@/components/Footer";
import { ContentProvider } from "@/lib/content";
import { SiteJsonLd } from "@/components/JsonLd";
import { Analytics } from "@/components/Analytics";
import { CookieConsent } from "@/components/CookieConsent";
import { ConversionTracker } from "@/components/ConversionTracker";
import { SupportChat } from "@/components/SupportChat";
import { WhatsAppButton } from "@/components/WhatsAppButton";
import { LeadMagnetPopup } from "@/components/LeadMagnetPopup";
import { site } from "@/lib/site";

export const metadata: Metadata = {
  metadataBase: new URL(`https://${site.domain}`),
  title: {
    default: `${site.company} — IT Services, Hardware & SAVIO AI`,
    template: `%s — ${site.company}`,
  },
  description:
    "Technomate IT-Solution delivers managed IT services, laptops & hardware, and SAVIO — an AI System Administrator that automates IT support with telemetry, self-healing and enterprise knowledge.",
  keywords: [
    "IT services",
    "managed IT",
    "laptop supplier",
    "hardware provider",
    "AI IT automation",
    "AI System Administrator",
    "AI System Admin",
    "AI sysadmin",
    "SAVIO",
    "self-healing IT",
    "Technomate",
  ],
  openGraph: {
    title: `${site.company} — IT Services, Hardware & SAVIO AI`,
    description:
      "Managed IT services, hardware supply, and SAVIO — the AI System Administrator that fixes IT before your team even notices.",
    type: "website",
    url: `https://${site.domain}`,
    siteName: site.company,
    locale: "en_IN",
    images: [
      {
        url: "/og.png",
        width: 1200,
        height: 630,
        alt: `${site.company} — ${site.productTagline}`,
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: `${site.company} — IT Services, Hardware & SAVIO AI`,
    description:
      "Managed IT services, hardware supply, and SAVIO — the AI System Administrator that fixes IT before your team even notices.",
    images: ["/og.png"],
  },
  // The Technomate mark, cropped from public/logo.png (not the full wordmark,
  // which is unreadable at tab size).
  icons: {
    icon: [{ url: "/favicon.png", type: "image/png", sizes: "256x256" }],
    apple: [{ url: "/apple-touch-icon.png", sizes: "180x180" }],
  },
  alternates: { canonical: "/" },
};

// Apply saved / preferred theme before first paint to avoid a flash.
const themeScript = `(function(){try{var t=localStorage.getItem('tm-theme')||'system';var d=t==='dark'||(t==='system'&&window.matchMedia('(prefers-color-scheme: dark)').matches);document.documentElement.classList.toggle('dark',d);}catch(e){}})();`;

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link
          rel="preconnect"
          href="https://fonts.gstatic.com"
          crossOrigin="anonymous"
        />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap"
          rel="stylesheet"
        />
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body>
        <SiteJsonLd />
        <ContentProvider>
          <Navbar />
          <main>{children}</main>
          <Footer />
          {/* Floats above every page. Reads the same content layer as the rest of the
              site, so it answers with what the pages already say. */}
          <SupportChat />
          <WhatsAppButton />
          <LeadMagnetPopup />
        </ContentProvider>
        <Analytics />
        <ConversionTracker />
        <CookieConsent />
      </body>
    </html>
  );
}
