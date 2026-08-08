"use client";

import Link from "next/link";
import { Mail, Phone, MapPin, Linkedin, Twitter, Instagram } from "lucide-react";
import { nav, site } from "@/lib/site";
import { BrandLogo } from "./BrandLogo";
import { useContent, Rich } from "@/lib/content";

export function Footer() {
  const { c, list } = useContent();
  const email = c("contactInfo.email", site.contact.email);
  const phone = c("contactInfo.phone", site.contact.phone);
  const addressLines = list<string>(
    "contactInfo.addressLines",
    site.contact.addressLines as unknown as string[],
  );

  return (
    <footer className="border-t border-token bg-surface">
      <div className="mx-auto max-w-6xl px-5 py-14 sm:px-8">
        <div className="grid gap-10 md:grid-cols-4">
          <div className="md:col-span-2">
            <Link href="/" className="inline-flex items-center">
              <BrandLogo className="h-20 sm:h-24" />
            </Link>
            <p className="mt-4 max-w-sm text-sm leading-relaxed text-secondary-token">
              <Rich
                text={c(
                  "brand.footerBlurb",
                  "Managed IT services, laptops & hardware, and **Astra** — the AI System Administrator that resolves IT issues before your team even notices.",
                )}
              />
            </p>
            <div className="mt-5 flex gap-3">
              <a
                href={site.social.linkedin}
                aria-label="LinkedIn"
                className="grid h-9 w-9 place-items-center rounded-lg border border-token text-secondary-token hover:text-brand-500"
              >
                <Linkedin className="h-[18px] w-[18px]" />
              </a>
              <a
                href={site.social.twitter}
                aria-label="Twitter / X"
                className="grid h-9 w-9 place-items-center rounded-lg border border-token text-secondary-token hover:text-brand-500"
              >
                <Twitter className="h-[18px] w-[18px]" />
              </a>
              <a
                href={site.social.instagram}
                aria-label="Instagram"
                className="grid h-9 w-9 place-items-center rounded-lg border border-token text-secondary-token hover:text-brand-500"
              >
                <Instagram className="h-[18px] w-[18px]" />
              </a>
            </div>
          </div>

          <div>
            <h4 className="text-sm font-semibold">
              {c("nav.companyHeading", "Company")}
            </h4>
            <ul className="mt-4 space-y-2.5 text-sm">
              {nav.map((item) => (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    className="text-secondary-token hover:text-brand-500"
                  >
                    {c(`nav.${item.href.slice(1)}`, item.label)}
                  </Link>
                </li>
              ))}
              <li>
                <Link
                  href="/compare"
                  className="text-secondary-token hover:text-brand-500"
                >
                  {c("nav.compare", "Compare")}
                </Link>
              </li>
              <li>
                <a
                  href={site.appUrl}
                  className="text-secondary-token hover:text-brand-500"
                >
                  {c("nav.loginSignup", "Login / Sign up")}
                </a>
              </li>
            </ul>
          </div>

          <div>
            <h4 className="text-sm font-semibold">
              {c("nav.contactHeading", "Contact")}
            </h4>
            <ul className="mt-4 space-y-3 text-sm text-secondary-token">
              <li className="flex items-start gap-2.5">
                <MapPin className="mt-0.5 h-4 w-4 shrink-0 text-brand-500" />
                <span>{addressLines.join(", ")}</span>
              </li>
              <li className="flex items-center gap-2.5">
                <Mail className="h-4 w-4 shrink-0 text-brand-500" />
                <a href={`mailto:${email}`} className="hover:text-brand-500">
                  {email}
                </a>
              </li>
              <li className="flex items-center gap-2.5">
                <Phone className="h-4 w-4 shrink-0 text-brand-500" />
                <a
                  href={`tel:${phone.replace(/\s/g, "")}`}
                  className="hover:text-brand-500"
                >
                  {phone}
                </a>
              </li>
            </ul>
          </div>
        </div>

        <div className="mt-12 flex flex-col items-center justify-between gap-3 border-t border-token pt-6 text-sm text-muted-token sm:flex-row">
          <p>
            © {new Date().getFullYear()} {c("brand.company", site.company)}. All
            rights reserved.
          </p>
          <p>{c("brand.footerProduct", `${site.product} — ${site.productTagline}`)}</p>
        </div>
      </div>
    </footer>
  );
}
