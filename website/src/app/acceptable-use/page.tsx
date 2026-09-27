import type { Metadata } from "next";
import { LegalPage } from "@/components/LegalPage";
import { site } from "@/lib/site";

export const metadata: Metadata = {
  title: "Acceptable Use Policy",
  description:
    "What ASTRA may and may not be used for, including the rules for remote support sessions and remediation.",
  alternates: { canonical: "/acceptable-use/" },
};

export default function AcceptableUsePage() {
  return (
    <LegalPage
      title="Acceptable Use Policy"
      effective="2026-09-26"
      reviewed
      intro={
        <>
          ASTRA can see into, and act on, the computers people use every day. This policy
          sets out what it may be used for. It forms part of the{" "}
          <a href="/terms/">Terms of Service</a>, and applies to every user of a
          customer&rsquo;s account.
        </>
      }
    >
      <h2>1. Devices and people</h2>
      <p>You must not use ASTRA to:</p>
      <ul>
        <li>enrol, monitor or act on a device your organisation does not own or control;</li>
        <li>
          monitor people who have not been given the notice your local law requires, or
          for any purpose other than supporting, securing and managing your IT;
        </li>
        <li>
          harass, stalk or covertly surveil anyone, or gather information about a
          person&rsquo;s private life.
        </li>
      </ul>

      <h2>2. Remote support</h2>
      <ul>
        <li>
          Request a session only to help the person at the device, and give the real
          reason in the request &mdash; they read it before deciding.
        </li>
        <li>
          Do not pressure anyone into accepting, or ask again after they have said no.
        </li>
        <li>
          Do not access, copy or photograph personal information you happen to see on the
          screen, beyond what the support task requires.
        </li>
        <li>End the session as soon as the task is done.</li>
      </ul>

      <h2>3. The platform itself</h2>
      <p>You must not:</p>
      <ul>
        <li>
          try to bypass the approval tiers, the action allowlist, the consent prompt, or
          any other control;
        </li>
        <li>
          probe, scan or test the security of the service without our written permission
          &mdash; report suspected vulnerabilities to{" "}
          <a href={`mailto:${site.contact.security}`}>{site.contact.security}</a> instead;
        </li>
        <li>
          access another organisation&rsquo;s data, share accounts, or give access to
          anyone outside your organisation other than your authorised IT providers;
        </li>
        <li>
          reverse engineer the service or the agent, except where the law expressly
          allows it;
        </li>
        <li>
          overload the service, use it to send spam, or use it to distribute malware;
        </li>
        <li>use it to break any law, or to infringe anyone else&rsquo;s rights.</li>
      </ul>

      <h2>4. AI features</h2>
      <p>
        Do not use ASTRA&rsquo;s assistant to generate content that is unlawful, harmful
        or deceptive, or attempt to make it ignore its safety rules. Review what it
        proposes before approving an action &mdash; approval tiers exist so a person makes
        the decision.
      </p>

      <h2>5. Enforcement</h2>
      <p>
        If we reasonably believe this policy has been broken, we may suspend the account
        or the affected user, feature or device, and will tell you why. Serious or
        repeated breaches allow us to terminate under the Terms of Service. We may report
        unlawful activity to the authorities.
      </p>

      <h2>6. Reporting misuse</h2>
      <p>
        If you believe ASTRA is being misused &mdash; including on a device you use
        &mdash; write to{" "}
        <a href={`mailto:${site.legal.grievanceOfficer.email}`}>
          {site.legal.grievanceOfficer.email}
        </a>
        .
      </p>
    </LegalPage>
  );
}
