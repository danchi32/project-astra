"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { Menu, X, ArrowRight } from "lucide-react";
import { nav, site } from "@/lib/site";
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
    // Not fixed: the header scrolls away with the page. It therefore needs its
    // own background rather than the translucent overlay treatment.
    <header className="relative z-50 border-b border-token bg-surface">
      {/* The bar stays at its normal height — only the logo is scaled up, so it
          fills the bar rather than forcing it taller. */}
      <nav className="mx-auto flex h-20 max-w-6xl items-center justify-between px-5 sm:px-8">
        <Link href="/" className="flex items-center">
          <BrandLogo className="h-14 sm:h-16" />
        </Link>

        <div className="hidden items-center gap-1 md:flex">
          {nav.map((item) => {
            const active = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "rounded-lg px-3.5 py-2 text-sm font-medium transition-colors",
                  active
                    ? "text-brand-500"
                    : "text-secondary-token hover:text-primary-token",
                )}
              >
                {c(`nav.${item.href.slice(1)}`, item.label)}
              </Link>
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
        <div className="border-b border-token bg-surface md:hidden">
          <div className="space-y-1 px-5 py-4">
            {nav.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className="block rounded-lg px-3 py-2.5 text-sm font-medium text-secondary-token hover:bg-surface-2 hover:text-primary-token"
              >
                {c(`nav.${item.href.slice(1)}`, item.label)}
              </Link>
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
