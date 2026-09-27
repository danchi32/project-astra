import type { Metadata } from "next";
import { LegalPage } from "@/components/LegalPage";
import { site } from "@/lib/site";

export const metadata: Metadata = {
  title: "Data Processing Agreement",
  description:
    "How Technomate IT-Solution Private Limited processes personal data on behalf of ASTRA customers: instructions, security, sub-processors, breaches, transfers and deletion.",
  alternates: { canonical: "/dpa/" },
};

export default function DpaPage() {
  const { legal } = site;
  return (
    <LegalPage
      title="Data Processing Agreement"
      effective="2026-09-26"
      reviewed
      intro={
        <>
          This agreement forms part of the <a href="/terms/">Terms of Service</a> between{" "}
          {legal.displayName} (&ldquo;Technomate&rdquo;, the <strong>Processor</strong>)
          and the organisation using ASTRA (the &ldquo;Customer&rdquo;, the{" "}
          <strong>Data Fiduciary</strong> or controller). It applies whenever Technomate
          processes personal data on the Customer&rsquo;s behalf. Customers who need a
          countersigned copy can request one from{" "}
          <a href={`mailto:${site.contact.privacy}`}>{site.contact.privacy}</a>.
        </>
      }
    >
      <h2>1. Scope of processing</h2>
      <table>
        <thead>
          <tr>
            <th>Item</th>
            <th>Detail</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>Subject matter</td>
            <td>Provision of the ASTRA IT operations service under the Terms of Service</td>
          </tr>
          <tr>
            <td>Duration</td>
            <td>The term of the Customer&rsquo;s subscription, plus the deletion period in section 9</td>
          </tr>
          <tr>
            <td>Nature and purpose</td>
            <td>
              Device inventory and telemetry collection, AI-assisted diagnosis, approved
              remediation, consented remote support, reporting, notifications and audit
              logging
            </td>
          </tr>
          <tr>
            <td>Data principals</td>
            <td>
              The Customer&rsquo;s employees, contractors and other people who use enrolled
              devices or the ASTRA portal
            </td>
          </tr>
          <tr>
            <td>Personal data</td>
            <td>
              Names, work email addresses, signed-in Windows usernames and security IDs,
              device hostnames, support conversation text, approval and audit records, and
              the live screen content of a remote support session while it is open (not
              stored)
            </td>
          </tr>
          <tr>
            <td>Sensitive data</td>
            <td>
              None is intended. The agent does not read documents, email, browsing history
              or keystrokes
            </td>
          </tr>
        </tbody>
      </table>

      <h2>2. Instructions</h2>
      <p>
        Technomate processes personal data only on the Customer&rsquo;s documented
        instructions. The Terms of Service, this agreement, and the Customer&rsquo;s
        configuration of ASTRA (including enabled approval tiers and remote support) are
        those instructions. If Technomate believes an instruction breaks the law, it will
        say so and may decline to follow it. Technomate will not use the Customer&rsquo;s
        personal data for its own purposes, sell it, or use it to train AI models.
      </p>

      <h2>3. Customer responsibilities</h2>
      <p>
        The Customer is responsible for having a lawful basis for the processing, for
        giving its personnel the notice the law requires, and for the accuracy of the
        instructions it gives &mdash; including who may approve remediation and request
        remote support sessions.
      </p>

      <h2>4. Confidentiality</h2>
      <p>
        Technomate ensures that everyone it authorises to process the personal data is
        bound by a duty of confidentiality, and that access is limited to those who need
        it to provide or support the service.
      </p>

      <h2>5. Security</h2>
      <p>Technomate maintains at least the following measures:</p>
      <ul>
        <li>Encryption in transit (TLS) for all traffic between agent, portal and backend.</li>
        <li>Encryption at rest for the database and for stored third-party credentials.</li>
        <li>Logical separation of every organisation&rsquo;s data, enforced on every request.</li>
        <li>
          Role-based access control, short-lived access tokens, and rotating refresh
          tokens with reuse detection.
        </li>
        <li>
          Per-device agent credentials; remediation limited to a fixed allowlist enforced
          by both server and agent; signed agent updates.
        </li>
        <li>
          Remote support only with the device user&rsquo;s live consent, not recorded,
          with file transfer and command-line access disabled.
        </li>
        <li>Audit logging of every change and every command sent to a device.</li>
        <li>Automatic deletion of raw telemetry after 7 days.</li>
      </ul>

      <h2>6. Sub-processors</h2>
      <p>
        The Customer authorises Technomate to use the sub-processors listed on the{" "}
        <a href="/sub-processors/">sub-processors page</a>. Technomate binds each one to
        data-protection obligations no less protective than this agreement and remains
        responsible for their performance. Technomate will update that page at least 30
        days before a new sub-processor starts processing Customer personal data, and
        will email account administrators who have asked for notice. The Customer may
        object on reasonable data-protection grounds within that period; if the parties
        cannot resolve the objection, the Customer may terminate the affected service and
        receive a refund of prepaid fees for the unused period.
      </p>

      <h2>7. Assistance</h2>
      <p>
        Taking into account the nature of the processing, Technomate will help the
        Customer respond to requests from data principals exercising their rights, and
        with any data-protection impact assessment or consultation with a regulator that
        concerns the service. A request Technomate receives directly about Customer data
        is passed to the Customer, not answered by Technomate.
      </p>

      <h2>8. Personal data breaches</h2>
      <p>
        Technomate will notify the Customer without undue delay, and in any case within 72
        hours, after becoming aware of a breach affecting Customer personal data. The
        notice will describe what happened, the data and people likely affected, the
        likely consequences, and the steps taken or proposed. Technomate will keep the
        Customer updated as it learns more and cooperate with the Customer&rsquo;s own
        notifications to the Data Protection Board of India and affected individuals.
      </p>

      <h2>9. Deletion and return</h2>
      <p>
        On termination the Customer may export its data for 30 days. Technomate then
        deletes Customer personal data from its live systems, and backup copies expire
        within a further 30 days, unless the law requires Technomate to keep a record for
        longer &mdash; in which case it is kept only for that purpose.
      </p>

      <h2>10. Transfers outside India</h2>
      <p>
        Customer data is hosted in Singapore, and some sub-processors operate in other
        countries, as listed on the sub-processors page. Technomate transfers personal
        data only to countries not restricted by the Government of India under the Digital
        Personal Data Protection Act, 2023. Where the Customer is subject to the EU or UK
        GDPR, the parties will, on request, enter into the applicable Standard Contractual
        Clauses, which will take precedence over this agreement to the extent they
        conflict.
      </p>

      <h2>11. Audits</h2>
      <p>
        Technomate will make available the information reasonably needed to demonstrate
        compliance with this agreement, including completed security questionnaires and
        summaries of independent security testing. Where that is not sufficient, the
        Customer may, once a year and with 30 days&rsquo; notice, audit Technomate&rsquo;s
        compliance, at its own cost, during business hours, and subject to
        confidentiality.
      </p>

      <h2>12. Liability and precedence</h2>
      <p>
        Liability under this agreement is subject to the limits in the Terms of Service.
        If this agreement conflicts with the Terms of Service on the processing of
        personal data, this agreement prevails.
      </p>

      <h2>13. Contact</h2>
      <p>
        Privacy questions: <a href={`mailto:${site.contact.privacy}`}>{site.contact.privacy}</a>
        <br />
        Grievance Officer: {legal.grievanceOfficer.name},{" "}
        <a href={`mailto:${legal.grievanceOfficer.email}`}>{legal.grievanceOfficer.email}</a>
        <br />
        {legal.displayName}, {legal.registeredOffice.join(", ")}
      </p>
    </LegalPage>
  );
}
