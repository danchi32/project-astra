import type { Metadata } from "next";
import { LegalPage, CounselTodo } from "@/components/LegalPage";
import { site } from "@/lib/site";

export const metadata: Metadata = {
  title: "Terms of Service",
  description:
    "The agreement between Technomate IT-Solution Private Limited and customers of the ASTRA platform.",
  alternates: { canonical: "/terms/" },
};

export default function TermsPage() {
  const { legal } = site;
  return (
    <LegalPage
      title="Terms of Service"
      effective="2026-08-27"
      intro={
        <>
          These terms govern your organisation&rsquo;s use of ASTRA, supplied by{" "}
          {legal.displayName}. Please read <strong>section 4</strong> carefully: ASTRA
          executes commands on your computers, and section 4 is where you authorise that
          and decide who may approve it.
        </>
      }
    >
      <h2>1. Parties and acceptance</h2>
      <p>
        This agreement is between {legal.displayName}, a company incorporated in India
        under CIN {legal.cin}, with its registered office at{" "}
        {legal.registeredOffice.join(", ")} (&ldquo;Technomate&rdquo;), and the
        organisation that creates an ASTRA account (&ldquo;Customer&rdquo;,
        &ldquo;you&rdquo;).
      </p>
      <p>
        You accept these terms when you create an account, and the person doing so
        confirms they are authorised to bind the Customer. We record the version you
        accepted and the date of acceptance.
      </p>

      <h2>2. The service</h2>
      <p>
        ASTRA is a software-as-a-service platform for managing Windows device fleets. It
        comprises a hosted backend, a web portal for administrators, and a Windows agent
        installed on your devices. Its functions include hardware and software inventory,
        performance telemetry, patch visibility, compliance reporting, AI-assisted
        diagnosis, and automated remediation subject to section 4.
      </p>

      <h2>3. Accounts, users and licences</h2>
      <ul>
        <li>
          You are responsible for your administrators&rsquo; credentials and for the acts
          of anyone using your account.
        </li>
        <li>
          The service is licensed per device. You purchase a number of licences, and
          device enrolment is capped at that number.
        </li>
        <li>
          You must give accurate billing and tax information, and keep it up to date.
        </li>
      </ul>

      <h2>4. Authorisation for remote execution &mdash; please read</h2>

      <h3>4.1 What you are authorising</h3>
      <p>
        The ASTRA agent installs on your devices and runs with elevated system privileges.
        On your instruction and in accordance with the tier settings you configure, it{" "}
        <strong>executes commands on those devices</strong>. This includes restarting
        applications and services, clearing temporary files, resetting network components,
        repairing installed software, deploying updates, and disabling a local user
        account as part of employee offboarding.
      </p>
      <p>
        By enrolling a device you authorise Technomate to perform those actions on it.
      </p>

      <h3>4.2 The three tiers</h3>
      <p>
        Every action ASTRA can perform belongs to exactly one tier. The tier is fixed in
        our software and cannot be raised or lowered by the AI:
      </p>
      <table>
        <thead>
          <tr>
            <th>Tier</th>
            <th>Meaning</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>
              <strong>Automatic</strong>
            </td>
            <td>
              Safe, reversible actions that may run without a human approving each one, if
              you enable automatic approval.
            </td>
          </tr>
          <tr>
            <td>
              <strong>Approval required</strong>
            </td>
            <td>
              Runs only after one of your authorised people approves that specific action.
            </td>
          </tr>
          <tr>
            <td>
              <strong>Admin only</strong>
            </td>
            <td>
              Higher-risk actions that only an administrator of your organisation may
              approve. These are never dispatched automatically under any configuration.
            </td>
          </tr>
        </tbody>
      </table>
      <p>
        Tier enforcement happens in our backend, in code. It is not a matter of instructing
        the AI politely. A lower tier can never be used to perform a higher-tier action.
      </p>

      <h3>4.3 Your responsibilities</h3>
      <p>You confirm that:</p>
      <ul>
        <li>
          you own or otherwise control every device on which you install the agent, and
          are entitled to authorise this software to run on it;
        </li>
        <li>
          you have given your personnel whatever notice, and obtained whatever consent,
          applicable law requires for the collection of device data described in the{" "}
          <a href="/privacy/">Privacy Policy</a>;
        </li>
        <li>
          you have decided which tiers are enabled and which of your people may approve
          each tier, and you will keep that list current;
        </li>
        <li>
          you maintain your own backups. ASTRA is a management tool, not a backup service.
        </li>
      </ul>

      <h3>4.4 Kill switch</h3>
      <p>
        You may disable automatic approval for your whole organisation at any time from
        the portal. We additionally operate volume limits that suspend automatic approval
        and cap remediation activity when an unusual burst is detected.
      </p>

      <h2>5. Data</h2>
      <p>
        You remain responsible for the data ASTRA processes for you. We process it only to
        provide the service and on your instructions. What we collect, where it is held,
        and for how long, is set out in the <a href="/privacy/">Privacy Policy</a>; the
        providers we rely on are listed on the{" "}
        <a href="/sub-processors/">sub-processors page</a>.
      </p>
      <p>
        <strong>Hosting location.</strong> The ASTRA application and database are hosted
        in <strong>Singapore</strong>. If your organisation requires data residency in
        India or elsewhere, raise it before you sign &mdash; we cannot change it after the
        fact.
      </p>
      <p>
        Customers requiring a Data Processing Agreement should contact{" "}
        <a href={`mailto:${site.contact.privacy}`}>{site.contact.privacy}</a>.
      </p>

      <h2>6. Fees, billing and taxes</h2>
      <p>
        Fees are as shown on the <a href="/pricing/">pricing page</a> or in your order.
        Trials, renewals, cancellation and refunds are governed by the{" "}
        <a href="/refund-policy/">Refund &amp; Cancellation Policy</a>.
      </p>
      <CounselTodo>
        Complete the billing terms once the payment rail is live: currency by region,
        whether prices are exclusive of GST and other applicable taxes, payment period,
        consequences of non-payment, and which entity is the seller of record for
        international sales where a Merchant of Record is used.
      </CounselTodo>

      <h2>7. Intellectual property</h2>
      <p>
        ASTRA, including the backend, portal, agent, documentation and all associated
        intellectual property, is and remains the property of {legal.displayName}. You are
        granted a non-exclusive, non-transferable right to use it for your internal
        business purposes for the term of your subscription. Installation and use of the
        Windows agent is additionally subject to the <a href="/eula/">Agent EULA</a>.
      </p>
      <p>
        Your data remains yours. We claim no ownership of it.
      </p>

      <h2>8. Acceptable use</h2>
      <p>
        You must not use ASTRA to access devices you do not control, to circumvent the
        tier controls, to reverse engineer the service, or in breach of applicable law.
      </p>

      <h2>9. Warranties, liability and indemnity</h2>
      <CounselTodo>
        This section must be drafted by counsel and is deliberately left unfinished. It
        needs, at minimum: the service warranty and its disclaimers; a limitation of
        liability with an appropriate cap; and specific treatment of{" "}
        <strong>liability for remediation outcomes</strong> &mdash; loss or damage arising
        from an action executed on a customer device. That last item is the distinguishing
        risk of this product and a generic software liability clause does not address it.
        Coordinate the cap with the professional indemnity cover actually held.
      </CounselTodo>

      <h2>10. Term, suspension and termination</h2>
      <CounselTodo>
        Term and renewal mechanics; suspension for non-payment or abuse; termination for
        cause and for convenience; and what happens to customer data on termination
        &mdash; the return-or-delete commitment and the window for it.
      </CounselTodo>

      <h2>11. Governing law and disputes</h2>
      <CounselTodo>
        Governing law and the forum for disputes. The registered office is in Uttar
        Pradesh; confirm the jurisdiction clause and whether arbitration is preferred.
      </CounselTodo>

      <h2>12. Changes to these terms</h2>
      <p>
        We may update these terms. Material changes will be notified to account
        administrators before they take effect, and the effective date above will change.
      </p>

      <h2>13. Contact</h2>
      <p>
        {legal.displayName}
        <br />
        {legal.registeredOffice.join(", ")}
        <br />
        <a href={`mailto:${legal.email}`}>{legal.email}</a> &middot; {legal.phone}
      </p>
    </LegalPage>
  );
}
