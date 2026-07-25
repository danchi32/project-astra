import { site } from "@/lib/site";

/**
 * JSON-LD structured data for rich results. Rendered as static <script> tags
 * (works with `output: export`). One graph site-wide (Organization + WebSite),
 * plus a SoftwareApplication node on the Astra product page.
 */

function JsonLdScript({ data }: { data: object }) {
  return (
    <script
      type="application/ld+json"
      // Structured data is trusted, build-time content — safe to inline.
      dangerouslySetInnerHTML={{ __html: JSON.stringify(data) }}
    />
  );
}

// Real social profiles only — placeholder "#" values are dropped.
const sameAs = Object.values(site.social).filter((u) => u && u !== "#");

export function SiteJsonLd() {
  const base = `https://${site.domain}`;
  const graph = {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "Organization",
        "@id": `${base}/#organization`,
        name: site.company,
        url: base,
        logo: `${base}/logo.png`,
        image: `${base}/logo.png`,
        email: site.contact.email,
        telephone: site.contact.phone,
        address: {
          "@type": "PostalAddress",
          streetAddress: "Ayodhya Ganj, Dadri",
          addressLocality: "Greater Noida",
          addressRegion: "Uttar Pradesh",
          postalCode: "203207",
          addressCountry: "IN",
        },
        contactPoint: {
          "@type": "ContactPoint",
          telephone: site.contact.phone,
          contactType: "sales",
          email: site.contact.sales,
          areaServed: "IN",
          availableLanguage: ["en", "hi"],
        },
        ...(sameAs.length ? { sameAs } : {}),
      },
      {
        "@type": "WebSite",
        "@id": `${base}/#website`,
        url: base,
        name: site.company,
        publisher: { "@id": `${base}/#organization` },
      },
    ],
  };
  return <JsonLdScript data={graph} />;
}

export function AstraJsonLd() {
  const base = `https://${site.domain}`;
  const data = {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    name: site.product,
    applicationCategory: "BusinessApplication",
    operatingSystem: "Windows",
    url: `${base}/astra/`,
    description:
      "Astra is an AI System Administrator that automates IT support: asset inventory, live telemetry, AI reasoning, and tiered self-healing across your entire Windows fleet.",
    publisher: { "@id": `${base}/#organization` },
    offers: {
      "@type": "Offer",
      priceCurrency: "INR",
      price: "0",
      description: "Per-seat licensing — see pricing page for current plans.",
      url: `${base}/pricing/`,
    },
  };
  return <JsonLdScript data={data} />;
}
