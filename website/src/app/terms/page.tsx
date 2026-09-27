import type { Metadata } from "next";
import { LegalPage } from "@/components/LegalPage";
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
      effective="2026-09-26"
      reviewed
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

      <h3>4.4 Remote support</h3>
      <p>
        Where your plan includes remote support and it is switched on for your
        organisation, your authorised technicians may ask to view and control an enrolled
        device&rsquo;s screen. Each session starts only after the person at the device
        accepts an on-screen prompt naming the technician and the reason, is not recorded,
        has file transfer and command-line access disabled, and is logged in your audit
        trail. Only your people can start a session; ASTRA&rsquo;s AI cannot. You are
        responsible for deciding who in your organisation may request sessions and for
        how your technicians use them.
      </p>

      <h3>4.5 Kill switch</h3>
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
        Where we process personal data for you, the{" "}
        <a href="/dpa/">Data Processing Agreement</a> applies and forms part of these
        terms. Customers who need a countersigned copy should contact{" "}
        <a href={`mailto:${site.contact.privacy}`}>{site.contact.privacy}</a>.
      </p>

      <h2>6. Fees, billing and taxes</h2>
      <p>
        Fees are as shown on the <a href="/pricing/">pricing page</a> or in your order.
        Trials, renewals, cancellation and refunds are governed by the{" "}
        <a href="/refund-policy/">Refund &amp; Cancellation Policy</a>.
      </p>
      <ul>
        <li>
          <strong>Currency and seller.</strong> Customers in India are billed in Indian
          rupees by {legal.displayName} through Razorpay. International customers are
          billed in US dollars through Paddle, which acts as Merchant of Record: Paddle is
          the seller on those transactions, issues the invoice, and handles the
          applicable sales taxes. International customers who pay through PayPal buy
          from {legal.displayName} directly.
        </li>
        <li>
          <strong>Taxes.</strong> Prices are exclusive of GST and other applicable taxes,
          which are added to the invoice at the rate in force.
        </li>
        <li>
          <strong>Payment.</strong> Subscriptions are paid in advance for each monthly or
          annual period and renew automatically until cancelled. Invoiced customers pay
          within 15 days of the invoice date.
        </li>
        <li>
          <strong>Non-payment.</strong> If a payment fails or is overdue, we will tell you
          and allow 7 days to settle it. After that the account becomes read-only
          &mdash; you can still sign in and export your data, but remediation and new
          enrolments stop &mdash; until the balance is paid.
        </li>
      </ul>

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
        The full rules are in the <a href="/acceptable-use/">Acceptable Use Policy</a>,
        which forms part of these terms.
      </p>

      <h2>9. Warranties, liability and indemnity</h2>

      <h3>9.1 Our warranty</h3>
      <p>
        We will provide the service with reasonable skill and care, and it will perform
        materially as described in its documentation. If it does not, tell us: we will
        correct the problem or, if we cannot within a reasonable time, you may terminate
        and receive a refund of fees prepaid for the period after termination. That is
        your remedy for a breach of this warranty.
      </p>
      <p>
        Otherwise, and to the extent the law allows, the service is provided &ldquo;as
        is&rdquo;. We do not warrant that it will be uninterrupted or error-free, or that
        the AI&rsquo;s diagnoses will always be correct &mdash; which is why actions that
        change a device are governed by the tiers in section 4.
      </p>

      <h3>9.2 Remediation outcomes</h3>
      <p>
        ASTRA changes a device only through the actions in its fixed catalogue, at the
        tier you configured. We are responsible for each action doing what its catalogue
        entry says. We are not responsible for the consequences of an action you or your
        people approved, or enabled for automatic approval, where the action did what it
        describes. If an agent release we publish causes a device fault, we will withdraw
        or correct it promptly and help you restore affected devices at no charge.
      </p>

      <h3>9.3 Limitation of liability</h3>
      <ul>
        <li>
          Each party&rsquo;s total liability arising out of or in connection with this
          agreement, in any 12-month period, is limited to the fees you paid or were due
          to pay us in the 12 months before the event giving rise to the claim.
        </li>
        <li>
          Neither party is liable for indirect, special or consequential loss, loss of
          profits, revenue or goodwill, or loss of data that could have been restored from
          a backup you are required to keep under section 4.3.
        </li>
        <li>
          These limits do not apply to your obligation to pay fees, to either
          party&rsquo;s indemnity under 9.4, or to liability that cannot be limited by
          law, including for fraud.
        </li>
      </ul>

      <h3>9.4 Indemnities</h3>
      <p>
        We will defend you against a third-party claim that the service infringes that
        party&rsquo;s intellectual property rights, and pay any resulting damages awarded.
        You will defend us against a third-party claim arising from your installing the
        agent on a device you were not entitled to control, or from failing to give your
        personnel the notice or obtain the consent section 4.3 requires. The party seeking
        protection must notify the other promptly and let it control the defence.
      </p>

      <h2>10. Term, suspension and termination</h2>
      <ul>
        <li>
          <strong>Term.</strong> This agreement starts when you create an account and
          continues through your trial and every paid period, renewing automatically
          until either party ends it.
        </li>
        <li>
          <strong>Cancellation.</strong> You may cancel at any time from the Billing page;
          the subscription runs to the end of the paid period, as set out in the{" "}
          <a href="/refund-policy/">Refund &amp; Cancellation Policy</a>. We may end the
          agreement for convenience on 30 days&rsquo; written notice, refunding any
          prepaid fees for the unused period.
        </li>
        <li>
          <strong>Suspension.</strong> We may suspend the service for non-payment (after
          the notice in section 6), or immediately where needed to stop a security threat
          or a breach of section 8. We will restore it once the cause is resolved.
        </li>
        <li>
          <strong>Termination for cause.</strong> Either party may terminate if the other
          materially breaches this agreement and does not fix the breach within 30 days
          of written notice.
        </li>
        <li>
          <strong>Your data on termination.</strong> For 30 days after termination your
          account stays available read-only so you can export your data. After that we
          delete it from the live system, and backup copies expire within a further 30
          days, except where the law requires us to keep records longer.
        </li>
        <li>
          Sections 5, 7, 9, 11 and anything else that by its nature should survive,
          survive termination.
        </li>
      </ul>

      <h2>11. Governing law and disputes</h2>
      <p>
        This agreement is governed by the laws of India. The parties will first try to
        resolve any dispute by good-faith discussion between senior representatives for
        30 days. A dispute not resolved that way will be referred to a sole arbitrator
        appointed by mutual agreement under the Arbitration and Conciliation Act, 1996.
        The seat and venue of arbitration is Gautam Budh Nagar, Uttar Pradesh, and the
        proceedings are in English. Subject to that, the courts at Gautam Budh Nagar,
        Uttar Pradesh have exclusive jurisdiction. Either party may seek urgent interim
        relief from a competent court.
      </p>

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
