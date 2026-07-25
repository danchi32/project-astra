# Technomate IT Solution — Marketing Website

Public marketing site for **technomateai.com**. Next.js 15 (App Router) + Tailwind CSS + framer-motion, sharing the ASTRA portal's design tokens (blue brand, Inter, dark/light).

## Pages

| Route | Purpose |
|---|---|
| `/` | Home — services + Astra overview with animated hero |
| `/about` | About Technomate — IT service provider & hardware supplier |
| `/astra` | Astra product page — full feature showcase with animated demos |
| `/pricing` | Astra plans & packages (placeholder tiers) |
| `/contact` | Inquiry form + address |
| Login / Sign up | Links to `astra.technomateai.com` (the product app) |

## Develop

```bash
cd website
npm install
npm run dev      # http://localhost:3100
```

## Things to customize

- **Contact details, app URL, socials** → `src/lib/site.ts`
- **Pricing numbers / plan features** → `src/components/PricingPlans.tsx`
- **Contact form delivery** → `src/components/ContactForm.tsx` (currently falls back to a
  prefilled `mailto:`; wire it to your API / Formspree / CRM for real submissions)

## Build

```bash
npm run build && npm start
```

Deploys cleanly to Vercel (root directory: `website`).
