/**
 * Central site configuration — every page reads from this single source of truth.
 *
 * NAMING — three tiers, deliberately separate. Do not mix them.
 *
 *   product      "ASTRA"                                  the software itself
 *   company      "Technomate IT-Solution" / "Technomate"  marketing prose
 *   legal.name   "TECHNOMATE IT-SOLUTION PRIVATE LIMITED" footer, invoices,
 *                                                         contracts, EULA, installer
 *
 * The hyphen in "IT-Solution" is part of the registered name. It is not optional,
 * and it is the single most-repeated mistake in this codebase's history.
 */
export const site = {
  company: "Technomate IT-Solution",
  brandShort: "Technomate",
  domain: "technomateai.com",
  product: "ASTRA",
  productTagline: "Your AI System Administrator",
  // Login / Sign-up redirects to the ASTRA product app.
  appUrl: "https://astra.technomateai.com",

  // The ASTRA backend. The site chat widget calls its public assistant endpoint straight
  // from the browser — this is a static export, so there is no server here to proxy
  // through, and the value is baked in at build time (NEXT_PUBLIC_ASTRA_API_URL overrides
  // it when developing against a local backend). The API must list this site's origin in
  // ASTRA_MARKETING_ORIGINS, or the browser will block the call.
  apiUrl: "https://api.astra.technomateai.com",

  // Demo booking link (Cal.com / Calendly / Google — any provider). Paste the
  // full URL here to make every "Book a demo" CTA open it in a new tab. Leave
  // empty to fall back to the contact form.
  booking: "https://cal.com/astraai/30min",

  /**
   * The registered legal entity behind ASTRA.
   *
   * Companies Act 2013 s.12(3)(c), read with Rule 26 of the Companies (Incorporation)
   * Rules 2014, requires the company's name, registered office address, CIN, telephone
   * number and email to appear on business letters, billheads, notices and other
   * official publications. That is why this block exists and why the footer renders it.
   *
   * PAN and TAN are DELIBERATELY ABSENT. They identify the company but are not public
   * disclosures — they live in backend settings only and must never ship to a browser.
   * GSTIN is different: it is public and legally required on a tax invoice, so it
   * belongs here the moment it is issued.
   */
  legal: {
    name: "TECHNOMATE IT-SOLUTION PRIVATE LIMITED",
    // Title case for rendering. The all-caps form above is the registered spelling and
    // is what belongs in a contract; this one is what belongs in a footer.
    displayName: "Technomate IT-Solution Private Limited",
    cin: "U62099UW2026PTC257827",
    // Empty until GST registration completes. Every consumer of this value checks for a
    // non-empty string first, so nothing renders a blank "GSTIN:" label in the meantime.
    gstin: "",
    incorporatedOn: "2026-08-25",
    registeredOffice: [
      "Ayodhya Ganj, Dadri",
      "Gautam Budh Nagar",
      "Uttar Pradesh 203207",
      "India",
    ],
    email: "danish@technomateai.com",
    phone: "+91 97115 31786",
    // Published contact for data-protection complaints. A named, reachable grievance
    // officer is a required element of the privacy notice, not a courtesy.
    grievanceOfficer: {
      name: "Adeel Ahamad",
      email: "grievance@technomateai.com",
    },
  },

  // --- Contact details ---
  contact: {
    email: "astra@technomateai.com",
    sales: "sales@technomateai.com",
    // Where existing customers write. Kept separate from `email` so a support request
    // and a general enquiry can be routed to different people later without a code change.
    support: "support@technomateai.com",
    phone: "+91 97115 31786",
    addressLines: [
      "Technomate IT-Solution Private Limited",
      "Ayodhya Ganj, Dadri",
      "Gautam Budh Nagar",
      "Uttar Pradesh 203207",
      "India",
    ],
    hours: "Mon–Sat, 10:00 AM – 7:00 PM IST",
    // Where a security researcher should send a vulnerability report. Mirrors
    // ASTRA_SECURITY_CONTACT on the backend, which serves /.well-known/security.txt.
    security: "security@technomateai.com",
    privacy: "privacy@technomateai.com",
  },

  social: {
    linkedin: "https://www.linkedin.com/company/technomate-ai/",
    twitter: "#",
    instagram: "#",
  },
} as const;

/**
 * Resolved "Book a demo" target. If a booking URL is configured it opens in a
 * new tab; otherwise CTAs fall back to the contact page. Vendor-agnostic —
 * works with any Cal.com / Calendly / Google scheduling link.
 */
const bookingUrl = site.booking as string;
export const bookDemo = {
  href: bookingUrl.length > 0 ? bookingUrl : "/contact",
  external: bookingUrl.length > 0,
} as const;

export const nav = [
  { label: "About Us", href: "/about" },
  { label: "ASTRA", href: "/astra" },
  { label: "Pricing", href: "/pricing" },
  { label: "Blog", href: "/blog" },
  { label: "Contact", href: "/contact" },
] as const;

/**
 * Policy pages, rendered as their own footer column. Kept out of `nav` on purpose:
 * these belong in the footer, not the primary navigation.
 */
export const legalNav = [
  { label: "Privacy Policy", href: "/privacy" },
  { label: "Terms of Service", href: "/terms" },
  { label: "Refund & Cancellation", href: "/refund-policy" },
  { label: "Cookie Policy", href: "/cookies" },
  { label: "Agent EULA", href: "/eula" },
  { label: "Sub-processors", href: "/sub-processors" },
] as const;
