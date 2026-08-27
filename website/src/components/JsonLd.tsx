import { site } from "@/lib/site";
// Single source of truth for prices. Imported at build time rather than retyped here:
// this codebase has twice shipped stale prices because the number lived in more than one
// place, and structured data that disagrees with the pricing page is worse than none.
import pricing from "../../public/pricing.json";

/**
 * JSON-LD structured data for rich results. Rendered as static <script> tags
 * (works with `output: export`). One graph site-wide (Organization + WebSite),
 * plus a SoftwareApplication node on the ASTRA product page.
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
  const { legal } = site;
  const graph = {
    "@context": "https://schema.org",
    "@graph": [
      {
        // Corporation rather than the generic Organization: this is a registered
        // company, and `legalName` + `foundingDate` are what let search engines
        // reconcile the brand with the incorporated entity.
        "@type": "Corporation",
        "@id": `${base}/#organization`,
        name: site.company,
        legalName: legal.displayName,
        foundingDate: legal.incorporatedOn,
        // The Corporate Identity Number is the entity's registry identifier.
        identifier: {
          "@type": "PropertyValue",
          propertyID: "CIN",
          value: legal.cin,
        },
        // Present only once GST registration completes — an empty vatID is worse
        // than an absent one.
        ...(legal.gstin ? { vatID: legal.gstin } : {}),
        url: base,
        logo: `${base}/logo.png`,
        image: `${base}/logo.png`,
        email: legal.email,
        telephone: legal.phone,
        // The registered office, not a marketing address. These must agree with the
        // footer disclosure and with the MCA record.
        address: {
          "@type": "PostalAddress",
          streetAddress: "Ayodhya Ganj, Dadri",
          addressLocality: "Gautam Budh Nagar",
          addressRegion: "Uttar Pradesh",
          postalCode: "203207",
          addressCountry: "IN",
        },
        contactPoint: [
          {
            "@type": "ContactPoint",
            telephone: site.contact.phone,
            contactType: "sales",
            email: site.contact.sales,
            areaServed: "IN",
            availableLanguage: ["en", "hi"],
          },
          {
            "@type": "ContactPoint",
            contactType: "customer support",
            email: legal.grievanceOfficer.email,
            areaServed: "IN",
            availableLanguage: ["en", "hi"],
          },
        ],
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
  const monthly = Object.values(pricing).map((p) => p.monthly);
  const data = {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    name: site.product,
    applicationCategory: "BusinessApplication",
    operatingSystem: "Windows",
    url: `${base}/astra/`,
    description:
      "ASTRA is an AI System Administrator that automates IT support: asset inventory, live telemetry, AI reasoning, and tiered self-healing across your entire Windows fleet.",
    publisher: { "@id": `${base}/#organization` },
    // A range, in the currency actually charged. The previous node declared
    // priceCurrency "INR" with price "0" while the pricing page showed USD — a
    // contradiction that would have been read as a free product.
    offers: {
      "@type": "AggregateOffer",
      priceCurrency: "USD",
      lowPrice: Math.min(...monthly).toFixed(2),
      highPrice: Math.max(...monthly).toFixed(2),
      offerCount: monthly.length,
      description: "Per device, per month. See the pricing page for current plans.",
      url: `${base}/pricing/`,
    },
  };
  return <JsonLdScript data={data} />;
}
