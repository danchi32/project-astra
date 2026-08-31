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
    "@graph": [
      {
        "@type": "SoftwareApplication",
        "@id": `${base}/astra/#software`,
        name: site.product,
        alternateName: ["ASTRA AI System Administrator", "ASTRA AI System Admin"],
        applicationCategory: "BusinessApplication",
        applicationSubCategory: "AI system administration and endpoint management",
        operatingSystem: "Windows 10, Windows 11",
        url: `${base}/astra/`,
        description:
          "ASTRA is AI System Administrator software that diagnoses Windows endpoint issues, applies governed remediations, and verifies results with human approval controls.",
        publisher: { "@id": `${base}/#organization` },
        offers: {
          "@type": "AggregateOffer",
          priceCurrency: "USD",
          lowPrice: Math.min(...monthly).toFixed(2),
          highPrice: Math.max(...monthly).toFixed(2),
          offerCount: monthly.length,
          description: "Per device, per month. See the pricing page for current plans.",
          url: `${base}/pricing/`,
        },
      },
      {
        "@type": "FAQPage",
        "@id": `${base}/astra/#faq`,
        mainEntity: [
          ["Can an AI System Administrator replace a human IT administrator?", "No. ASTRA automates repeatable evidence collection and approved endpoint fixes. IT administrators retain control of sensitive, approval-required and admin-only actions."],
          ["How is an AI system admin different from an RMM tool?", "RMM platforms primarily monitor devices and run predefined automation. ASTRA adds an evidence-to-decision-to-verification loop, while enforcing allowlists, approval tiers and audit records."],
          ["Which devices can ASTRA manage?", "ASTRA is currently focused on business fleets running Windows 10 and Windows 11, including office and remote-work endpoints."],
          ["How can a company evaluate ASTRA safely?", "Start with a limited-device pilot, review collected telemetry and audit records, then expand only after the approval policy and remediation results meet your requirements."],
        ].map(([name, text]) => ({
          "@type": "Question",
          name,
          acceptedAnswer: { "@type": "Answer", text },
        })),
      },
    ],
  };
  return <JsonLdScript data={data} />;
}
