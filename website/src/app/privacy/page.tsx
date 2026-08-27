import type { Metadata } from "next";
import { LegalPage, CounselTodo } from "@/components/LegalPage";
import { site } from "@/lib/site";

export const metadata: Metadata = {
  title: "Privacy Policy",
  description:
    "How Technomate IT-Solution Private Limited collects, uses, stores and protects personal data across the ASTRA platform and this website.",
  alternates: { canonical: "/privacy/" },
};

export default function PrivacyPage() {
  const { legal } = site;
  return (
    <LegalPage
      title="Privacy Policy"
      effective="2026-08-27"
      intro={
        <>
          This policy explains how {legal.displayName} (&ldquo;Technomate&rdquo;,
          &ldquo;we&rdquo;, &ldquo;us&rdquo;) handles personal data. It covers three
          different situations, and our role is different in each &mdash; which is the
          most important thing to understand before reading the rest.
        </>
      }
    >
      <h2>1. The three relationships</h2>
      <table>
        <thead>
          <tr>
            <th>Situation</th>
            <th>Our role</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>
              You visit <strong>{site.domain}</strong> or contact us
            </td>
            <td>
              We are the <strong>Data Fiduciary</strong> (controller). We decide why and
              how your data is used.
            </td>
          </tr>
          <tr>
            <td>
              You are an administrator with an <strong>ASTRA account</strong>
            </td>
            <td>
              We are the <strong>Data Fiduciary</strong> for your account and billing
              details.
            </td>
          </tr>
          <tr>
            <td>
              You are an <strong>employee of an ASTRA customer</strong> and the agent runs
              on your work device
            </td>
            <td>
              Your employer is the Data Fiduciary. We are their{" "}
              <strong>Data Processor</strong> and act only on their instructions. Direct
              your questions to your employer&rsquo;s IT team first; we will support them
              in answering you.
            </td>
          </tr>
        </tbody>
      </table>

      <h2>2. What we collect</h2>

      <h3>2.1 Marketing website</h3>
      <ul>
        <li>
          <strong>Contact and demo forms:</strong> your name, work email, phone number,
          company, area of interest and message.
        </li>
        <li>
          <strong>Resource downloads:</strong> your email address.
        </li>
        <li>
          <strong>Campaign attribution:</strong> the referring page and any UTM parameters
          on the link that brought you here.
        </li>
        <li>
          <strong>Analytics and advertising cookies:</strong> see the{" "}
          <a href="/cookies/">Cookie Policy</a>.
        </li>
        <li>
          <strong>Website assistant:</strong> the questions you type. The assistant
          answers from published product information, creates no record of your
          conversation, and has no access to any customer&rsquo;s data.
        </li>
      </ul>

      <h3>2.2 ASTRA accounts</h3>
      <ul>
        <li>Organisation name; administrator name, work email and hashed password.</li>
        <li>
          Billing identity you enter: legal name, billing contact, address, and tax
          registration number where you provide one.
        </li>
        <li>Authentication and session records, and your acceptance of these terms.</li>
      </ul>

      <h3>2.3 Data the ASTRA agent collects from managed devices</h3>
      <p>
        Collected on our customers&rsquo; instruction, from devices they own or control:
      </p>
      <ul>
        <li>Device hostname, operating system version and hardware inventory.</li>
        <li>
          The <strong>username signed in</strong> to the device &mdash; this identifies a
          person, and we treat it accordingly.
        </li>
        <li>
          Performance telemetry &mdash; processor, memory and disk usage &mdash; sampled
          about once per minute.
        </li>
        <li>
          Installed applications, running services, Windows Update status, and
          system/application event log entries.
        </li>
        <li>
          Support conversations initiated from the device, and a record of every
          remediation action requested, approved and executed.
        </li>
        <li>Asset assignment records, where an organisation uses that feature.</li>
      </ul>
      <p>
        <strong>What the agent does not do:</strong> it does not capture keystrokes,
        record the screen, read the contents of documents or email, monitor browsing
        history, or access personal files.
      </p>

      <h2>3. Why we process it</h2>
      <ul>
        <li>To provide, secure, operate and support the ASTRA service.</li>
        <li>
          To diagnose faults and &mdash; where the customer has approved the relevant tier
          &mdash; to remediate them.
        </li>
        <li>To bill for the service and meet our accounting and tax obligations.</li>
        <li>
          To respond to enquiries and, where you have asked us to, send you information
          about the product.
        </li>
        <li>To detect and prevent abuse, and to keep an audit trail of what was done.</li>
      </ul>
      <CounselTodo>
        State the lawful basis for each purpose in the form the applicable
        data-protection legislation requires, and confirm the position on consent versus
        legitimate use for the marketing communications described above.
      </CounselTodo>

      <h2>4. Artificial intelligence</h2>
      <p>
        ASTRA uses a third-party large language model to reason about IT issues. When a
        support conversation or a diagnosis runs, the relevant conversation text and
        device telemetry are sent to that provider. Model providers are not permitted to
        train on data sent through the ASTRA service. Our providers are listed on the{" "}
        <a href="/sub-processors/">sub-processors page</a>.
      </p>
      <p>
        Actions that change a device are governed by approval tiers enforced in our
        backend, not by the model. The AI can propose a remediation; whether it may run
        without a human approving it is decided by the customer&rsquo;s configuration and
        checked in code.
      </p>

      <h2>5. Where data is held</h2>
      <p>
        The ASTRA application and database are hosted in <strong>Singapore</strong>. Some
        sub-processors operate elsewhere, including the United States. Full detail, with
        locations, is on the <a href="/sub-processors/">sub-processors page</a>.
      </p>
      <CounselTodo>
        Confirm the cross-border transfer position under applicable Indian law and, if the
        company sells into the EEA or the UK, add the transfer mechanism and any
        additional required disclosures.
      </CounselTodo>

      <h2>6. How long we keep it</h2>
      <table>
        <thead>
          <tr>
            <th>Data</th>
            <th>Retention</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>Raw performance telemetry</td>
            <td>7 days, then automatically deleted</td>
          </tr>
          <tr>
            <td>Daily aggregated telemetry (for trend charts)</td>
            <td>Retained for the life of the account</td>
          </tr>
          <tr>
            <td>Device inventory</td>
            <td>Replaced on each collection; deleted when the device is removed</td>
          </tr>
          <tr>
            <td>Audit logs and remediation history</td>
            <td>Retained for the life of the account</td>
          </tr>
          <tr>
            <td>Account and billing records</td>
            <td>
              Retained while the account is active, then for the period our tax and
              company-law obligations require
            </td>
          </tr>
          <tr>
            <td>Marketing enquiries</td>
            <td>Until you ask us to delete them</td>
          </tr>
        </tbody>
      </table>
      <CounselTodo>
        Confirm the statutory retention period for books of account and invoices, and
        state it as a definite number of years here.
      </CounselTodo>

      <h2>7. Security</h2>
      <ul>
        <li>
          Encryption in transit; encryption at rest for stored third-party credentials.
        </li>
        <li>
          Role-based access control, with every organisation&rsquo;s data isolated from
          every other.
        </li>
        <li>
          Short-lived access tokens with rotating refresh tokens and reuse detection.
        </li>
        <li>
          Remediation is restricted to a fixed catalogue of permitted actions, enforced
          independently by both the server and the agent. The agent executes action
          identifiers, never arbitrary commands.
        </li>
        <li>Audit logging of every change and every command sent to a device.</li>
      </ul>
      <p>
        To report a vulnerability, email{" "}
        <a href={`mailto:${site.contact.security}`}>{site.contact.security}</a>.
      </p>

      <h2>8. Your rights</h2>
      <p>
        Subject to applicable law you may ask us to give you a copy of your personal data,
        correct it, delete it, or withdraw a consent you previously gave. Write to{" "}
        <a href={`mailto:${site.contact.privacy}`}>{site.contact.privacy}</a>.
      </p>
      <p>
        If the data concerns a device managed by your employer, we will refer your request
        to them, because it is their data and their decision.
      </p>

      <h2>9. Grievance Officer</h2>
      <p>
        In accordance with applicable Indian law, the following officer may be contacted
        with any complaint about how your personal data has been handled:
      </p>
      <p>
        <strong>{legal.grievanceOfficer.name}</strong>
        <br />
        Grievance Officer, {legal.displayName}
        <br />
        <a href={`mailto:${legal.grievanceOfficer.email}`}>
          {legal.grievanceOfficer.email}
        </a>
        <br />
        {legal.registeredOffice.join(", ")}
      </p>
      <CounselTodo>
        Confirm the response timeline that must be committed to here.
      </CounselTodo>

      <h2>10. Changes</h2>
      <p>
        We will post any change to this policy on this page and update the effective date.
        Material changes affecting customers will additionally be notified as the
        applicable agreement requires.
      </p>
    </LegalPage>
  );
}
