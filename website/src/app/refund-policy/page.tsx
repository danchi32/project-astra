import type { Metadata } from "next";
import { LegalPage } from "@/components/LegalPage";
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
      effective="2026-09-26"
      reviewed
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
      <p>
        The 14-day free trial is how we let you evaluate ASTRA before paying, so paid
        subscriptions are <strong>not refundable</strong> once a billing period has
        started. That applies to monthly and annual plans, to partial periods, and to
        licences you bought but did not use. You can cancel at any time to stop the next
        renewal.
      </p>
      <p>We will refund you in full in these cases:</p>
      <ul>
        <li>
          <strong>Duplicate or incorrect charge</strong> &mdash; you were charged twice,
          or charged an amount different from your order.
        </li>
        <li>
          <strong>Service failure on our side</strong> &mdash; the service was materially
          unavailable or did not work as described for reasons within our control, and we
          could not fix it within a reasonable time after you reported it. We refund the
          fees for the affected period.
        </li>
        <li>
          <strong>We end the agreement for convenience</strong> &mdash; we refund the
          prepaid fees for the unused period, as the <a href="/terms/">Terms of
          Service</a> set out.
        </li>
      </ul>
      <p>
        Approved refunds go back to the original payment method within 7 working days of
        approval; your bank or card issuer may take a further 5&ndash;7 working days to
        show it. For international purchases made through Paddle, Paddle is the seller and
        processes the refund under its own buyer terms; we will raise it with Paddle on
        your behalf.
      </p>

      <h2>6. Taxes</h2>
      <ul>
        <li>
          Prices shown are <strong>exclusive of GST</strong> and other applicable taxes.
        </li>
        <li>
          Customers in India are billed in Indian rupees by {site.legal.displayName}. GST
          is added at the applicable rate and shown separately on the tax invoice, with our
          GSTIN and yours where you provide it.
        </li>
        <li>
          International customers are billed in US dollars. Through Paddle, which as
          Merchant of Record calculates, collects and remits any sales tax or VAT due in
          your country and issues the invoice; or through PayPal, where we issue the
          invoice.
        </li>
      </ul>

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
