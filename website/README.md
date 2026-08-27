# Technomate IT-Solution — Marketing Website

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
npm run dev      # http://localhost:3200
```

## Site assistant (the chat bubble)

`src/components/SupportChat.tsx` floats on every page and answers visitors' questions from
ASTRA's documentation — never from the model's own memory, so it cannot invent a price or
a promise. It posts to the ASTRA API:

`POST {site.apiUrl}/api/v1/public/assistant` → `{ answer, sources, grounded }`

Three things follow from that, and all three are easy to forget:

- **The answers are edited in the backend, not here.** Sales-side facts (pricing shape,
  trial, rollout, hardware, contact details) live in `backend/app/services/ai/public_faq.py`;
  product/support guides come from the help articles the operator publishes in the portal.
  When a fact changes on this site, change it there in the same commit.
- **The API must allow this origin.** `ASTRA_MARKETING_ORIGINS` on the backend defaults to
  `technomateai.com`, `www.technomateai.com` and `localhost:3200`. A new domain needs
  adding there or the browser blocks the call.
- **`site.apiUrl` is baked in at build time** (this is a static export).
  `NEXT_PUBLIC_ASTRA_API_URL` overrides it when developing against a local backend.

When the API is unreachable, or has nothing on the subject, the widget hands the visitor to
the contact form and the phone number rather than guessing.

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
