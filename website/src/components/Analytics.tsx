import Script from "next/script";

/**
 * GA4 + Microsoft Clarity, both gated on their IDs so they stay inert until
 * configured. Values are read from build-time env vars (NEXT_PUBLIC_*). The GA
 * measurement ID falls back to the known production ID; Clarity stays off until
 * NEXT_PUBLIC_CLARITY_ID is set (paste it into .env.local).
 *
 * These IDs are public by design (they ship in the client bundle) — not secrets.
 */
const GA_ID = process.env.NEXT_PUBLIC_GA_ID ?? "G-GKPCWJGVEY";
const CLARITY_ID = process.env.NEXT_PUBLIC_CLARITY_ID ?? "";

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
gtag('config', '${GA_ID}');`}
          </Script>
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
