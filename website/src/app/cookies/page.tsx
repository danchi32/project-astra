import type { Metadata } from "next";
import { LegalPage } from "@/components/LegalPage";
import { site } from "@/lib/site";

export const metadata: Metadata = {
  title: "Cookie Policy",
  description:
    "The cookies and similar technologies used on technomateai.com and in the ASTRA portal, and how to control them.",
  alternates: { canonical: "/cookies/" },
};

export default function CookiesPage() {
  return (
    <LegalPage
      title="Cookie Policy"
      effective="2026-08-27"
      intro={
        <>
          This page lists the cookies and similar storage used on{" "}
          <strong>{site.domain}</strong> and in the ASTRA portal, what each is for, and
          how to control them.
        </>
      }
    >
      <h2>1. Strictly necessary</h2>
      <p>
        These are required for the site or the product to work. They cannot be switched
        off, and they are not used for advertising.
      </p>
      <table>
        <thead>
          <tr>
            <th>Name</th>
            <th>Where</th>
            <th>Purpose</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>
              <code>tm-theme</code>
            </td>
            <td>This website (local storage)</td>
            <td>Remembers your light or dark theme choice</td>
          </tr>
          <tr>
            <td>
              <code>astra_auth</code>
            </td>
            <td>ASTRA portal (cookie)</td>
            <td>Marks a signed-in session so the app can route you correctly</td>
          </tr>
          <tr>
            <td>
              <code>access_token</code>, <code>refresh_token</code>
            </td>
            <td>ASTRA portal (local storage)</td>
            <td>
              Keeps you signed in. Cleared when you sign out. Not used for tracking
            </td>
          </tr>
        </tbody>
      </table>

      <h2>2. Analytics and advertising</h2>
      <p>
        These operate on the marketing website only. They are <strong>not</strong> present
        in the ASTRA product, and they never receive customer device or telemetry data.
      </p>
      <table>
        <thead>
          <tr>
            <th>Provider</th>
            <th>Purpose</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>Google Analytics</td>
            <td>How visitors find and move through the site</td>
          </tr>
          <tr>
            <td>Google Ads</td>
            <td>Measuring which advertisements lead to an enquiry</td>
          </tr>
          <tr>
            <td>Meta Pixel</td>
            <td>Campaign measurement and retargeting</td>
          </tr>
          <tr>
            <td>Microsoft Clarity</td>
            <td>Aggregated usage analytics</td>
          </tr>
        </tbody>
      </table>

      <h2>3. Your choices</h2>
      <p>
        Non-essential cookies are set only where you have allowed them. You can change
        your choice at any time using the cookie banner, and your browser lets you block
        or delete cookies independently of anything we do.
      </p>
      <p>
        Blocking analytics and advertising cookies does not affect your ability to use the
        website or the product.
      </p>

      <h2>4. Contact</h2>
      <p>
        Questions about this policy:{" "}
        <a href={`mailto:${site.contact.privacy}`}>{site.contact.privacy}</a>. See also
        our <a href="/privacy/">Privacy Policy</a>.
      </p>
    </LegalPage>
  );
}
