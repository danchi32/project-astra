import type { Metadata } from "next";
import { LegalPage } from "@/components/LegalPage";
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
      effective="2026-09-26"
      reviewed
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
        history, or access personal files. The only way anyone sees a device&rsquo;s
        screen is a live remote support session that the person at the device has
        agreed to (section 2.4).
      </p>

      <h3>2.4 Remote support sessions</h3>
      <p>
        Where an organisation&rsquo;s plan includes remote support and it has been switched
        on for that organisation, one of its technicians can ask to view and control a
        managed device&rsquo;s screen to help the person using it. When that happens:
      </p>
      <ul>
        <li>
          <strong>The person at the device is asked first.</strong> A prompt titled
          &ldquo;ASTRA Remote Support&rdquo; appears on their screen, naming the technician
          and the reason they gave. Nothing connects unless they click Allow. If they do
          not answer within about two minutes the request lapses; silence is never treated
          as a yes.
        </li>
        <li>
          While the session is open, the technician sees the screen live and can use the
          mouse and keyboard. The clipboard is shared both ways so text can be copied
          between the two machines. File transfer and command-line access are disabled
          for these sessions.
        </li>
        <li>
          <strong>The session is not recorded.</strong> The screen is streamed to the
          technician in real time through our relay server and is not stored by us.
        </li>
        <li>
          We keep a record <em>about</em> the session &mdash; who asked, for which device,
          the reason given, whether the person allowed or declined, and when it started
          and ended &mdash; in the organisation&rsquo;s audit log.
        </li>
        <li>
          To make this possible a separate remote-support service is installed on the
          device, and only on devices of organisations that have the feature enabled. It
          is removed automatically when the feature is switched off.
        </li>
        <li>
          Remote support can only be started by a person. ASTRA&rsquo;s AI cannot request,
          start or join a remote session.
        </li>
      </ul>

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

      <h3>3.1 Lawful basis</h3>
      <table>
        <thead>
          <tr>
            <th>Purpose</th>
            <th>Basis</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>Providing, securing and supporting the ASTRA service</td>
            <td>
              Our contract with the customer; for device data, the customer&rsquo;s own
              lawful basis as Data Fiduciary, on whose instructions we act
            </td>
          </tr>
          <tr>
            <td>Remote support sessions</td>
            <td>
              The customer&rsquo;s instruction, together with the live consent of the
              person at the device, given separately for each session
            </td>
          </tr>
          <tr>
            <td>Billing, tax and accounting records</td>
            <td>Compliance with legal obligations</td>
          </tr>
          <tr>
            <td>Answering an enquiry you send us</td>
            <td>Your request, and the details you chose to give us for it</td>
          </tr>
          <tr>
            <td>Marketing email</td>
            <td>
              Your consent. Every such email carries an unsubscribe link, and you may
              withdraw consent at any time
            </td>
          </tr>
          <tr>
            <td>Analytics and advertising cookies</td>
            <td>
              Your consent, given through the cookie banner &mdash; see the{" "}
              <a href="/cookies/">Cookie Policy</a>
            </td>
          </tr>
          <tr>
            <td>Security, abuse prevention and the audit trail</td>
            <td>Legitimate uses permitted by law, and our contract with the customer</td>
          </tr>
        </tbody>
      </table>

      <h3>3.2 Who we share it with</h3>
      <p>
        We do not sell personal data, and we do not share it for other companies&rsquo;
        advertising. We share it only with:
      </p>
      <ul>
        <li>
          the providers listed on the <a href="/sub-processors/">sub-processors page</a>,
          under contract, and only as far as they need it to provide their service to us;
        </li>
        <li>systems the customer deliberately connects, such as their own helpdesk;</li>
        <li>
          a court, regulator or law-enforcement authority where the law requires it
          &mdash; where we are allowed to, we tell the affected customer first;
        </li>
        <li>
          a successor to our business, bound by this policy, if the company is merged or
          sold.
        </li>
      </ul>

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
      <p>
        We transfer personal data outside India only to countries not restricted by the
        Government of India under the Digital Personal Data Protection Act, 2023, and only
        to providers contractually bound to protect it to the standard in this policy.
        Customers who need a signed commitment on transfers can have one through our{" "}
        <a href="/dpa/">Data Processing Agreement</a>. If your organisation needs its data
        held in India, tell us before you sign.
      </p>

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
            <td>Remote support screen video</td>
            <td>Not stored &mdash; streamed live only</td>
          </tr>
          <tr>
            <td>Audit logs, remediation and remote-session history</td>
            <td>Retained for the life of the account</td>
          </tr>
          <tr>
            <td>Account and billing records</td>
            <td>
              Retained while the account is active, then for eight years from the end of
              the financial year they relate to, as Indian company and tax law requires
              for books of account
            </td>
          </tr>
          <tr>
            <td>Customer data after the account closes</td>
            <td>
              Available for export for 30 days, then deleted from the live system; backup
              copies expire within a further 30 days
            </td>
          </tr>
          <tr>
            <td>Marketing enquiries</td>
            <td>Until you ask us to delete them</td>
          </tr>
        </tbody>
      </table>

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
        You may also nominate someone to exercise these rights for you in the event of
        your death or incapacity. We answer requests within 30 days, may first need to
        confirm your identity, and do not charge for this.
      </p>
      <p>
        If the data concerns a device managed by your employer, we will refer your request
        to them, because it is their data and their decision.
      </p>
      <p>
        <strong>Children.</strong> ASTRA and this website are for businesses. We do not
        knowingly collect personal data from anyone under 18; if you believe we have,
        write to us and we will delete it.
      </p>
      <p>
        <strong>Breaches.</strong> If a breach affects personal data we hold, we inform
        affected customers without undue delay and within 72 hours of confirming it, and
        notify the Data Protection Board of India and affected individuals as the law
        requires.
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
      <p>
        We acknowledge a complaint within 48 hours and aim to resolve it within 30 days.
        If you are not satisfied with our response, you may complain to the Data
        Protection Board of India.
      </p>

      <h2>10. Changes</h2>
      <p>
        We will post any change to this policy on this page and update the effective date.
        Material changes affecting customers will additionally be notified as the
        applicable agreement requires.
      </p>
    </LegalPage>
  );
}
