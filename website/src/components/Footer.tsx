"use client";

import Link from "next/link";
import { Mail, MapPin, Phone, Headset, Linkedin, Twitter, Instagram } from "lucide-react";
import { nav, site } from "@/lib/site";
import { BrandLogo } from "./BrandLogo";
import { useContent, Rich } from "@/lib/content";

/**
 * A simple four-pane glyph for the platform badge.
 *
 * Deliberately generic geometry rather than a reproduction of any vendor's logo: it
 * reads as "Windows" at this size without borrowing a mark we have no licence to.
 */
function WindowsGlyph({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden className={className} fill="currentColor">
      <path d="M3 5.4 10.4 4.3v7.2H3V5.4Zm8.6-1.3L21 3v8.5h-9.4V4.1ZM3 12.5h7.4v7.2L3 18.6v-6.1Zm8.6 0H21V21l-9.4-1.1v-7.4Z" />
    </svg>
  );
}

/** One entry in the contact strip. */
function ContactItem({
  icon,
  label,
  value,
  href,
  prefix,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  href: string;
  prefix?: string;
}) {
  return (
    <div className="flex items-start gap-3">
      <span className="mt-0.5 grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-white/15 text-white">
        {icon}
      </span>
      <div className="min-w-0">
        <p className="text-[11px] font-semibold uppercase tracking-wider text-white/70">
          {label}
        </p>
        <a
          href={href}
          className="block truncate text-sm font-medium text-white hover:underline"
        >
          {prefix ? <span className="mr-1">{prefix}</span> : null}
          {value}
        </a>
      </div>
    </div>
  );
}

export function Footer() {
  const { c, list } = useContent();
  const support = c("contactInfo.support", site.contact.support);
  const phone = c("contactInfo.phone", site.contact.phone);
  const sales = c("contactInfo.sales", site.contact.sales);
  const hours = c("contactInfo.hours", site.contact.hours);
  const addressLines = list<string>(
    "contactInfo.addressLines",
    site.contact.addressLines as unknown as string[],
  );

  // Placeholder "#" entries are dropped rather than rendered as dead icons — the same
  // rule the structured data already applies to `sameAs`.
  const socials = [
    { href: site.social.linkedin, label: "LinkedIn", Icon: Linkedin },
    { href: site.social.twitter, label: "Twitter / X", Icon: Twitter },
    { href: site.social.instagram, label: "Instagram", Icon: Instagram },
  ].filter((s) => s.href && s.href !== "#");

  const product = [
    { label: "ASTRA", href: "/astra" },
    { label: "Pricing", href: "/pricing" },
    { label: "Compare", href: "/compare" },
  ];
  const company = [
    { label: "About Us", href: "/about" },
    { label: "Contact Us", href: "/contact" },
  ];
  const resources = [
    { label: "Blog", href: "/blog" },
    { label: "Security & Trust", href: "/security" },
    { label: "Offboarding checklist", href: "/resources/offboarding-checklist" },
  ];

  return (
    <footer className="border-t border-token bg-surface">
      <div className="mx-auto max-w-6xl px-5 py-14 sm:px-8">
        {/* ── Brand + link columns ─────────────────────────────────────── */}
        <div className="grid gap-10 md:grid-cols-12">
          <div className="md:col-span-5">
            <Link href="/" className="inline-flex items-center">
              <BrandLogo className="h-20 sm:h-24" />
            </Link>
            <p className="mt-4 max-w-sm text-sm leading-relaxed text-secondary-token">
              <Rich
                text={c(
                  "brand.footerBlurb",
                  "Managed IT services, laptops & hardware, and **ASTRA** — the AI System Administrator that resolves IT issues before your team even notices.",
                )}
              />
            </p>

            {/* Platform availability. One entry, because the agent is Windows-only —
                listing platforms it does not run on would be a claim we cannot keep. */}
            <div className="mt-6 inline-flex items-center gap-3 rounded-xl border border-token bg-surface-2 px-4 py-2.5">
              <WindowsGlyph className="h-5 w-5 text-brand-600" />
              <div className="leading-tight">
                <p className="text-sm font-semibold text-primary-token">
                  {c("footer.platform", "Available for Windows")}
                </p>
                <p className="text-[11px] text-muted-token">
                  {c("footer.platformNote", "Windows 10 and 11 · 64-bit")}
                </p>
              </div>
            </div>
          </div>

          <div className="md:col-span-7">
            <div className="grid grid-cols-2 gap-8 sm:grid-cols-3">
              {[
                { heading: c("nav.productHeading", "Product"), items: product },
                { heading: c("nav.companyHeading", "Company"), items: company },
                { heading: c("nav.resourcesHeading", "Resources"), items: resources },
              ].map((col) => (
                <div key={col.heading}>
                  <h4 className="text-sm font-semibold">{col.heading}</h4>
                  <ul className="mt-4 space-y-2.5 text-sm">
                    {col.items.map((item) => (
                      <li key={item.href}>
                        <Link
                          href={item.href}
                          className="text-secondary-token hover:text-brand-500"
                        >
                          {item.label}
                        </Link>
                      </li>
                    ))}
                    {col.heading === c("nav.companyHeading", "Company") && (
                      <li>
                        <a
                          href={site.appUrl}
                          className="text-secondary-token hover:text-brand-500"
                        >
                          {c("nav.loginSignup", "Login / Sign up")}
                        </a>
                      </li>
                    )}
                  </ul>
                </div>
              ))}
            </div>

          </div>
        </div>

        {/* ── Contact strip ────────────────────────────────────────────── */}
        <div
          className="mt-12 rounded-2xl px-6 py-6 sm:px-8"
          style={{
            background:
              "linear-gradient(120deg, #7f2599 0%, #9a2fbb 40%, #b246d4 70%, #e04ad0 100%)",
          }}
        >
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            <ContactItem
              icon={<Phone className="h-4 w-4" />}
              label={c("footer.callLabel", "Call us on")}
              value={phone}
              prefix="🇮🇳"
              href={`tel:${phone.replace(/\s/g, "")}`}
            />
            <ContactItem
              icon={<Mail className="h-4 w-4" />}
              label={c("footer.salesLabel", "For sales")}
              value={sales}
              href={`mailto:${sales}`}
            />
            <ContactItem
              icon={<Headset className="h-4 w-4" />}
              label={c("footer.supportLabel", "For support")}
              value={support}
              href={`mailto:${support}`}
            />
          </div>
          <div className="mt-5 flex flex-col gap-2 border-t border-white/20 pt-4 text-xs text-white/80 sm:flex-row sm:items-start sm:justify-between">
            <p className="flex items-start gap-2">
              <MapPin className="mt-px h-3.5 w-3.5 shrink-0" />
              <span>{addressLines.join(", ")}</span>
            </p>
            <p className="shrink-0 sm:text-right">{hours}</p>
          </div>
        </div>

        {/* ── Bottom bar ───────────────────────────────────────────────── */}
        <div className="mt-10 flex flex-col gap-5 border-t border-token pt-6 text-sm text-muted-token lg:flex-row lg:items-center lg:justify-between">
          <p>
            © {new Date().getFullYear()} {site.legal.displayName}. All rights reserved.
          </p>

          <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
            <Link href="/terms" className="hover:text-brand-500">
              Terms and conditions
            </Link>
            <Link href="/privacy" className="hover:text-brand-500">
              Privacy Policy
            </Link>
            <Link href="/refund-policy" className="hover:text-brand-500">
              Refunds
            </Link>
          </div>

          {socials.length > 0 && (
            <div className="flex items-center gap-3">
              <span className="text-xs">{c("footer.followUs", "Follow us on:")}</span>
              {socials.map(({ href, label, Icon }) => (
                <a
                  key={label}
                  href={href}
                  aria-label={label}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="grid h-8 w-8 place-items-center rounded-full border border-token text-secondary-token hover:border-brand-500 hover:text-brand-500"
                >
                  <Icon className="h-4 w-4" />
                </a>
              ))}
            </div>
          )}
        </div>
      </div>
    </footer>
  );
}
