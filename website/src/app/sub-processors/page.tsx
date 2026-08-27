import type { Metadata } from "next";
import { LegalPage, CounselTodo } from "@/components/LegalPage";
import { site } from "@/lib/site";

export const metadata: Metadata = {
  title: "Sub-processors",
  description:
    "The third-party providers ASTRA uses to deliver the service, what each one processes, and where it is located.",
  alternates: { canonical: "/sub-processors/" },
};

export default function SubProcessorsPage() {
  return (
    <LegalPage
      title="Sub-processors"
      effective="2026-08-27"
      intro={
        <>
          When you use ASTRA, {site.legal.displayName} processes data on your behalf. To
          do that we rely on the providers below. This page lists every one of them, what
          each processes, and where it is located.
        </>
      }
    >
      <h2>Infrastructure</h2>
      <table>
        <thead>
          <tr>
            <th>Provider</th>
            <th>Purpose</th>
            <th>Data processed</th>
            <th>Location</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>Google Cloud Platform</td>
            <td>Application hosting (Cloud Run) for the ASTRA API</td>
            <td>All service data in transit and in memory</td>
            <td>Singapore (asia-southeast1)</td>
          </tr>
          <tr>
            <td>Neon</td>
            <td>Managed PostgreSQL — the primary database</td>
            <td>All service data at rest</td>
            <td>Singapore (ap-southeast-1)</td>
          </tr>
          <tr>
            <td>Vercel</td>
            <td>Hosting for the ASTRA web portal</td>
            <td>Portal application delivery; no service data at rest</td>
            <td>Global edge network</td>
          </tr>
          <tr>
            <td>Hostinger</td>
            <td>Marketing website hosting and outbound mail relay</td>
            <td>Website content; contact-form submissions in transit</td>
            <td>Provider-managed</td>
          </tr>
        </tbody>
      </table>

      <h2>Artificial intelligence</h2>
      <table>
        <thead>
          <tr>
            <th>Provider</th>
            <th>Purpose</th>
            <th>Data processed</th>
            <th>Location</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>Anthropic</td>
            <td>
              The reasoning engine behind ASTRA&rsquo;s diagnosis and support chat
            </td>
            <td>
              Support conversation text and the device telemetry relevant to the issue
              being diagnosed
            </td>
            <td>United States</td>
          </tr>
        </tbody>
      </table>
      <p>
        ASTRA sends the model only what is needed to reason about the issue in front of
        it. Model providers are not permitted to train on data sent through the ASTRA
        service.
      </p>
      <CounselTodo>
        Confirm the exact contractual training-and-retention position with the model
        provider and restate it here in the provider&rsquo;s own terms.
      </CounselTodo>

      <h2>Communications</h2>
      <table>
        <thead>
          <tr>
            <th>Provider</th>
            <th>Purpose</th>
            <th>Data processed</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>Resend</td>
            <td>
              Transactional email delivery — verification codes, password resets, asset
              acknowledgements, notifications
            </td>
            <td>Recipient name and email address, message content</td>
          </tr>
          <tr>
            <td>Cal.com</td>
            <td>Demo scheduling from the marketing website</td>
            <td>Name, email and meeting details you enter when booking</td>
          </tr>
        </tbody>
      </table>

      <h2>Payments</h2>
      <CounselTodo>
        Complete this section once the payment rail is live. The intended arrangement is
        Razorpay for customers in India, with {site.legal.displayName} as the seller of
        record, and Paddle for international customers, where Paddle is the Merchant of
        Record and therefore the seller. That distinction changes who issues the invoice
        and who is responsible for transaction taxes, and it must be stated accurately.
      </CounselTodo>

      <h2>Marketing website analytics</h2>
      <p>
        These operate on <strong>{site.domain}</strong> only. They are not present in the
        ASTRA product, and they never receive customer device or telemetry data.
      </p>
      <ul>
        <li>Google Analytics and Google Ads — website usage and campaign measurement</li>
        <li>Meta Pixel — campaign measurement and retargeting</li>
        <li>Microsoft Clarity — aggregated usage analytics</li>
      </ul>
      <p>
        See the <a href="/cookies/">Cookie Policy</a> for how these are controlled.
      </p>

      <h2>Integrations you choose to enable</h2>
      <p>
        ASTRA can connect to your own helpdesk (currently Freshservice) if you configure
        it. That is a connection to <em>your</em> system, made on your instruction, and
        the provider is not our sub-processor — you remain the controller of anything
        sent there. Credentials you entrust to ASTRA for this purpose are encrypted at
        rest.
      </p>

      <h2>Changes to this list</h2>
      <p>
        We will update this page before a new sub-processor begins processing customer
        data. Customers with a signed Data Processing Agreement receive advance notice as
        set out in that agreement.
      </p>
      <p>
        Questions: <a href={`mailto:${site.contact.privacy}`}>{site.contact.privacy}</a>
      </p>
    </LegalPage>
  );
}
