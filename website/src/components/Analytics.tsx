"use client";

import { useEffect, useState } from "react";
import Script from "next/script";
import { effectiveConsent, onConsentChange } from "@/lib/consent";

/**
 * All marketing tags, each gated on its ID so it stays inert until configured, and now
 * additionally gated on the visitor's cookie consent.
 *
 * Two different gating mechanisms, because the vendors differ:
 *
 *   Google (GA4 + Ads)  loads always, but boots with Consent Mode v2 defaulting to
 *                       DENIED. Until consent is granted it sets no cookies and sends
 *                       only cookieless pings. This is Google's own recommended pattern
 *                       and it preserves modelled conversions, which a hard block does
 *                       not. `gtag('consent','update',…)` flips it when the visitor
 *                       accepts.
 *   Meta + Clarity      do not load at all until consent is granted. Neither has a
 *                       comparable consent-default mode, and Clarity records sessions.
 *
 * Values come from build-time env vars (NEXT_PUBLIC_*, public by design — they ship in
 * the client bundle, so they are not secrets).
 *
 *   NEXT_PUBLIC_GA_ID          GA4 measurement id (G-…) — has a prod default
 *   NEXT_PUBLIC_CLARITY_ID     Microsoft Clarity project id
 *   NEXT_PUBLIC_META_PIXEL_ID  Meta (Facebook/Instagram) Pixel id — for ads
 *   NEXT_PUBLIC_GOOGLE_ADS_ID  Google Ads id (AW-…) — remarketing + conversions
 */
const GA_ID = process.env.NEXT_PUBLIC_GA_ID ?? "G-GKPCWJGVEY";
const CLARITY_ID = process.env.NEXT_PUBLIC_CLARITY_ID ?? "";
// NOTE: use `||` not `??` — the CI/build env may set these to an EMPTY string
// (not undefined), and `??` would not fall back on "". `||` falls back on empty.
const META_PIXEL_ID = process.env.NEXT_PUBLIC_META_PIXEL_ID || "870269791759130";
const GOOGLE_ADS_ID = process.env.NEXT_PUBLIC_GOOGLE_ADS_ID || "AW-18354148692";

export function Analytics() {
  // Starts "denied" on every render, including the server's. The real value is read
  // after mount, so the markup cannot depend on localStorage and hydration stays stable.
  const [consent, setConsent] = useState<"granted" | "denied">("denied");

  useEffect(() => {
    setConsent(effectiveConsent());
    return onConsentChange(setConsent);
  }, []);

  // Push the current state into gtag whenever it changes, including the initial read.
  // Safe to call before the GA script has loaded: the bootstrap below creates
  // window.dataLayer first, and gtag replays the queue on load.
  useEffect(() => {
    const w = window as unknown as { gtag?: (...args: unknown[]) => void };
    w.gtag?.("consent", "update", {
      analytics_storage: consent,
      ad_storage: consent,
      ad_user_data: consent,
      ad_personalization: consent,
    });
  }, [consent]);

  const granted = consent === "granted";

  return (
    <>
      {GA_ID ? (
        <>
          {/* Must run BEFORE the gtag library, hence beforeInteractive: a default set
              after the library has already read storage is too late. */}
          <Script id="consent-default" strategy="beforeInteractive">
            {`window.dataLayer = window.dataLayer || [];
function gtag(){dataLayer.push(arguments);}
window.gtag = gtag;
gtag('consent', 'default', {
  ad_storage: 'denied',
  ad_user_data: 'denied',
  ad_personalization: 'denied',
  analytics_storage: 'denied',
  wait_for_update: 500
});`}
          </Script>
          <Script
            src={`https://www.googletagmanager.com/gtag/js?id=${GA_ID}`}
            strategy="afterInteractive"
          />
          <Script id="ga4-init" strategy="afterInteractive">
            {`gtag('js', new Date());
gtag('config', '${GA_ID}');${GOOGLE_ADS_ID ? `\ngtag('config', '${GOOGLE_ADS_ID}');` : ""}`}
          </Script>
        </>
      ) : null}

      {granted && META_PIXEL_ID ? (
        <>
          <Script id="meta-pixel" strategy="afterInteractive">
            {`!function(f,b,e,v,n,t,s){if(f.fbq)return;n=f.fbq=function(){n.callMethod?n.callMethod.apply(n,arguments):n.queue.push(arguments)};if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';n.queue=[];t=b.createElement(e);t.async=!0;t.src=v;s=b.getElementsByTagName(e)[0];s.parentNode.insertBefore(t,s)}(window,document,'script','https://connect.facebook.net/en_US/fbevents.js');
fbq('init','${META_PIXEL_ID}');fbq('track','PageView');`}
          </Script>
          <noscript>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              height="1"
              width="1"
              style={{ display: "none" }}
              alt=""
              src={`https://www.facebook.com/tr?id=${META_PIXEL_ID}&ev=PageView&noscript=1`}
            />
          </noscript>
        </>
      ) : null}

      {granted && CLARITY_ID ? (
        <Script id="ms-clarity" strategy="afterInteractive">
          {`(function(c,l,a,r,i,t,y){c[a]=c[a]||function(){(c[a].q=c[a].q||[]).push(arguments)};t=l.createElement(r);t.async=1;t.src="https://www.clarity.ms/tag/"+i;y=l.getElementsByTagName(r)[0];y.parentNode.insertBefore(t,y);})(window,document,"clarity","script","${CLARITY_ID}");`}
        </Script>
      ) : null}
    </>
  );
}
