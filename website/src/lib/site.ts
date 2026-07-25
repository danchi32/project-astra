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

export const nav = [
  { label: "About Us", href: "/about" },
  { label: "Astra", href: "/astra" },
  { label: "Pricing", href: "/pricing" },
  { label: "Contact", href: "/contact" },
] as const;
