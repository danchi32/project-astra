"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { Menu, X, ArrowRight, ChevronDown } from "lucide-react";
import { nav, site } from "@/lib/site";
import { serviceCategories } from "@/lib/services";
import { ThemeToggle } from "./ThemeToggle";
import { BrandLogo } from "./BrandLogo";
import { useContent } from "@/lib/content";
import { cn } from "@/lib/utils";

export function Navbar() {
  const { c } = useContent();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  // Close mobile menu on route change.
  useEffect(() => setOpen(false), [pathname]);

  return (
    // Not fixed: the header scrolls away with the page. Transparent rather than
    // filled, so the hero's aurora wash — which is pulled up behind it — shows
    // through. On pages without a hero the body background shows instead, which
    // is the colour it would have painted anyway.
    <header className="relative z-50">
      {/* The bar keeps its 64px height. The logo is larger than that and hangs
          past the bottom edge rather than stretching the bar — `self-start`
          anchors it to the top so the overhang falls downward, over the page
          rather than off the top of the viewport. Kept smaller on mobile, where
          a wider mark would run into the controls. */}
      <nav className="mx-auto flex h-16 max-w-6xl items-center justify-between px-5 sm:px-8">
        {/* data-brand-logo: where the about-page intro's logo flies to and lands. */}
        <Link href="/" data-brand-logo className="flex items-center self-start pt-2 sm:pt-3">
          <BrandLogo className="h-20 sm:h-28" />
        </Link>

        <div className="hidden items-center gap-1 md:flex">
          {nav.map((item) => {
            const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
            const link = (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-1 rounded-lg px-3.5 py-2 text-sm font-medium transition-colors",
                  active
                    ? "text-brand-500"
                    : "text-secondary-token hover:text-primary-token",
                )}
              >
                {c(`nav.${item.href.slice(1)}`, item.label)}
                {item.href === "/services" && (
                  <ChevronDown className="h-3.5 w-3.5 transition-transform group-hover:rotate-180" />
                )}
              </Link>
            );
            if (item.href !== "/services") return link;
            // Services opens a dropdown of every service page on hover / focus.
            return (
              <div key={item.href} className="group relative">
                {link}
                <div className="invisible absolute left-1/2 top-full z-50 w-[560px] -translate-x-1/2 pt-2 opacity-0 transition-all duration-200 group-focus-within:visible group-focus-within:opacity-100 group-hover:visible group-hover:opacity-100">
                  <div className="grid grid-cols-2 gap-1 rounded-2xl border border-token bg-surface p-2 shadow-2xl shadow-brand-600/10">
                    {serviceCategories.map((s) => (
                      <Link
                        key={s.href}
                        href={s.href}
                        className="flex gap-3 rounded-xl p-3 transition-colors hover:bg-surface-2"
                      >
                        <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-gradient-to-br from-brand-600 to-cyan-500 text-white">
                          <s.icon className="h-4 w-4" />
                        </span>
                        <span>
                          <span className="block text-sm font-semibold text-primary-token">{s.title}</span>
                          <span className="block text-xs text-muted-token">{s.short}</span>
                        </span>
                      </Link>
                    ))}
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        <div className="flex items-center gap-2.5">
          <ThemeToggle />
          <a
            href={site.appUrl}
            className="hidden items-center gap-1.5 rounded-lg border border-token bg-surface px-3.5 py-2 text-sm font-semibold transition-colors hover:border-brand-500/50 sm:inline-flex"
          >
            {c("nav.login", "Login")}
          </a>
          <a
            href={site.appUrl}
            className="hidden items-center gap-1.5 rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white shadow-lg shadow-brand-600/25 transition-all hover:bg-brand-500 md:inline-flex"
          >
            {c("nav.signup", "Sign up")} <ArrowRight className="h-4 w-4" />
          </a>
          <button
            type="button"
            aria-label="Toggle menu"
            onClick={() => setOpen((v) => !v)}
            className="grid h-9 w-9 place-items-center rounded-lg border border-token bg-surface md:hidden"
          >
            {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>
      </nav>

      {/* Mobile menu */}
      {open && (
        <div className="border-b border-token bg-app md:hidden">
          <div className="space-y-1 px-5 py-4">
            {nav.map((item) => (
              <div key={item.href}>
                <Link
                  href={item.href}
                  className="block rounded-lg px-3 py-2.5 text-sm font-medium text-secondary-token hover:bg-surface-2 hover:text-primary-token"
                >
                  {c(`nav.${item.href.slice(1)}`, item.label)}
                </Link>
                {item.href === "/services" && (
                  <div className="ml-3 border-l border-token pl-2">
                    {serviceCategories.map((s) => (
                      <Link
                        key={s.href}
                        href={s.href}
                        className="flex items-center gap-2 rounded-lg px-3 py-2 text-xs text-muted-token hover:bg-surface-2 hover:text-primary-token"
                      >
                        <s.icon className="h-3.5 w-3.5 text-brand-500" /> {s.title}
                      </Link>
                    ))}
                  </div>
                )}
              </div>
            ))}
            <div className="flex gap-2 pt-2">
              <a
                href={site.appUrl}
                className="flex-1 rounded-lg border border-token bg-surface px-4 py-2.5 text-center text-sm font-semibold"
              >
                {c("nav.login", "Login")}
              </a>
              <a
                href={site.appUrl}
                className="flex-1 rounded-lg bg-brand-600 px-4 py-2.5 text-center text-sm font-semibold text-white"
              >
                {c("nav.signup", "Sign up")}
              </a>
            </div>
          </div>
        </div>
      )}
    </header>
  );
}
