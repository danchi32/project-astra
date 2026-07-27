import Script from "next/script";

/**
 * All marketing tags, each gated on its ID so it stays inert until configured.
 * Values come from build-time env vars (NEXT_PUBLIC_*, public by design — they
 * ship in the client bundle, so they are not secrets).
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
  return (
    <>
      {GA_ID ? (
        <>
          <Script
            src={`https://www.googletagmanager.com/gtag/js?id=${GA_ID}`}
            strategy="afterInteractive"
          />
          <Script id="ga4-init" strategy="afterInteractive">
            {`window.dataLayer = window.dataLayer || [];
function gtag(){dataLayer.push(arguments);}
gtag('js', new Date());
gtag('config', '${GA_ID}');${GOOGLE_ADS_ID ? `\ngtag('config', '${GOOGLE_ADS_ID}');` : ""}`}
          </Script>
        </>
      ) : null}

      {META_PIXEL_ID ? (
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

      {CLARITY_ID ? (
        <Script id="ms-clarity" strategy="afterInteractive">
          {`(function(c,l,a,r,i,t,y){c[a]=c[a]||function(){(c[a].q=c[a].q||[]).push(arguments)};t=l.createElement(r);t.async=1;t.src="https://www.clarity.ms/tag/"+i;y=l.getElementsByTagName(r)[0];y.parentNode.insertBefore(t,y);})(window,document,"clarity","script","${CLARITY_ID}");`}
        </Script>
      ) : null}
    </>
  );
}
