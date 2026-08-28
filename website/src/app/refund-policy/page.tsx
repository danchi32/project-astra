import type { Metadata } from "next";
import { LegalPage, CounselTodo } from "@/components/LegalPage";
import { site } from "@/lib/site";

export const metadata: Metadata = {
  title: "Refund & Cancellation Policy",
  description:
    "Trial terms, billing cycles, cancellation and refund eligibility for ASTRA subscriptions.",
  alternates: { canonical: "/refund-policy/" },
};

export default function RefundPolicyPage() {
  return (
    <LegalPage
      title="Refund &amp; Cancellation Policy"
      effective="2026-08-27"
      intro={
        <>
          How trials, billing, cancellation and refunds work for ASTRA subscriptions from{" "}
          {site.legal.displayName}. This policy forms part of the{" "}
          <a href="/terms/">Terms of Service</a>.
        </>
      }
    >
      <h2>1. Free trial</h2>
      <ul>
        <li>New organisations start with a 14-day free trial.</li>
        <li>No payment details are required to begin the trial.</li>
        <li>
          The trial is not charged and does not convert to a paid subscription by itself
          &mdash; you choose a plan when you are ready.
        </li>
        <li>
          If you do not subscribe, the account moves to a read-only state at the end of
          the trial.
        </li>
      </ul>

      <h2>2. How billing works</h2>
      <ul>
        <li>
          ASTRA is licensed <strong>per device, per month</strong>. You purchase a number
          of licences and are billed on that number, whether or not every licence is in
          use.
        </li>
        <li>Monthly and annual billing cycles are available. Annual is billed up front.</li>
        <li>
          Device enrolment is capped at your licence count. To enrol more devices, add
          licences.
        </li>
      </ul>

      <h2>3. Changing your plan</h2>
      <ul>
        <li>
          You may add licences at any time. Additional licences are available immediately.
        </li>
        <li>
          You may reduce licences or change plan at any time. Reductions take effect from
          the next billing cycle; the current period is not re-rated.
        </li>
      </ul>

      <h2>4. Cancellation</h2>
      <ul>
        <li>You may cancel at any time from the Billing page in the ASTRA portal.</li>
        <li>
          Cancellation stops future renewals. Your subscription continues to the end of
          the period you have already paid for.
        </li>
        <li>
          After the paid period ends, the account becomes read-only. You can still sign in
          and export your data.
        </li>
        <li>
          Uninstalling the agent from your devices is separate from cancelling &mdash;
          please do both.
        </li>
      </ul>

      <h2>5. Refunds</h2>
      <CounselTodo>
        Set the refund position before the payment rail goes live. Decide and state: any
        money-back window for a first paid month; whether annual plans are refundable and
        on what basis; the position on partial periods and unused licences; how a refund
        for a service failure attributable to us is handled; and the timeline for
        processing an approved refund back to the original payment method. Note that the
        answer differs by rail &mdash; where a Merchant of Record is the seller for
        international sales, their refund mechanics apply and must be described
        accurately.
      </CounselTodo>

      <h2>6. Taxes</h2>
      <CounselTodo>
        State whether displayed prices are inclusive or exclusive of GST and other
        applicable taxes, the currency charged in each region, and how tax is shown on the
        invoice. This section cannot be completed until GST registration is issued.
      </CounselTodo>

      <h2>7. How to request a refund or raise a billing issue</h2>
      <p>
        Email <a href={`mailto:${site.contact.sales}`}>{site.contact.sales}</a> from the
        address associated with your account, quoting your organisation name and the
        invoice number. We will acknowledge and tell you the outcome and, where a refund
        is approved, when to expect it.
      </p>
      <p>
        If you are not satisfied with how a billing complaint has been handled, you may
        escalate to our Grievance Officer,{" "}
        {site.legal.grievanceOfficer.name}, at{" "}
        <a href={`mailto:${site.legal.grievanceOfficer.email}`}>
          {site.legal.grievanceOfficer.email}
        </a>
        .
      </p>
    </LegalPage>
  );
}
