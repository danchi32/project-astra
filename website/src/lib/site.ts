/**
 * Central site configuration. Edit the placeholder contact details and the
 * Astra app URL here — every page reads from this single source of truth.
 */
export const site = {
  company: "Technomate IT Solution",
  brandShort: "Technomate",
  domain: "technomateai.com",
  product: "Astra",
  productTagline: "Your AI System Administrator",
  // Login / Sign-up redirects to the Astra product app.
  appUrl: "https://astra.technomateai.com",

  // The Astra backend. The site chat widget calls its public assistant endpoint straight
  // from the browser — this is a static export, so there is no server here to proxy
  // through, and the value is baked in at build time (NEXT_PUBLIC_ASTRA_API_URL overrides
  // it when developing against a local backend). The API must list this site's origin in
  // ASTRA_MARKETING_ORIGINS, or the browser will block the call.
  apiUrl: "https://api.astra.technomateai.com",

  // Demo booking link (Cal.com / Calendly / Google — any provider). Paste the
  // full URL here to make every "Book a demo" CTA open it in a new tab. Leave
  // empty to fall back to the contact form.
  booking: "https://cal.com/astraai/30min",

  // --- Contact details ---
  contact: {
    email: "astra@technomateai.com",
    sales: "sales@technomateai.com",
    phone: "+91 97115 31786",
    addressLines: [
      "Technomate IT Solution",
      "Ayodhya Ganj, Dadri",
      "Greater Noida, Uttar Pradesh 203207",
      "India",
    ],
    hours: "Mon–Sat, 10:00 AM – 7:00 PM IST",
  },

  social: {
    linkedin: "#",
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
  { label: "Astra", href: "/astra" },
  { label: "Pricing", href: "/pricing" },
  { label: "Blog", href: "/blog" },
  { label: "Contact", href: "/contact" },
] as const;
