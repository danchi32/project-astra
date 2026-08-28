import type { Metadata } from "next";
import { LegalPage, CounselTodo } from "@/components/LegalPage";
import { site } from "@/lib/site";

export const metadata: Metadata = {
  title: "ASTRA Agent — End User Licence Agreement",
  description:
    "Licence terms for the ASTRA Windows agent installed on managed devices.",
  alternates: { canonical: "/eula/" },
};

export default function EulaPage() {
  const { legal } = site;
  return (
    <LegalPage
      title="ASTRA Agent — End User Licence Agreement"
      effective="2026-08-27"
      intro={
        <>
          These terms govern the ASTRA Windows agent &mdash; the software installed on
          managed devices. They are separate from the{" "}
          <a href="/terms/">Terms of Service</a>, which govern the hosted platform,
          because this is software that runs on <em>your</em> computers.
        </>
      }
    >
      <h2>1. Licence</h2>
      <p>
        {legal.displayName} grants you a non-exclusive, non-transferable, revocable
        licence to install and run the ASTRA agent on devices you own or control, for the
        number of licences covered by your active subscription and for its duration.
      </p>

      <h2>2. What the agent is, and what it does</h2>
      <p>The agent has two parts:</p>
      <ul>
        <li>
          a <strong>Windows service</strong> that runs with system privileges and performs
          machine-level work;
        </li>
        <li>
          a <strong>tray application</strong> that runs in the signed-in user&rsquo;s
          session and provides the support chat.
        </li>
      </ul>
      <p>It:</p>
      <ul>
        <li>
          reports device inventory, performance telemetry, installed software, services,
          Windows Update status and event log entries to the ASTRA platform;
        </li>
        <li>
          <strong>executes remediation actions on the device</strong>, drawn from a fixed
          catalogue built into the agent, at the approval tier configured by the
          organisation that enrolled it;
        </li>
        <li>updates itself from a cryptographically signed release channel.</li>
      </ul>
      <p>
        The agent executes <strong>action identifiers</strong> from its own built-in
        allowlist. It does not accept or run arbitrary commands, and it rejects anything
        outside that list &mdash; including from our own servers.
      </p>

      <h2>3. What the agent does not do</h2>
      <p>
        It does not capture keystrokes, record the screen, read the contents of documents
        or email, monitor browsing history, or access personal files.
      </p>

      <h2>4. Deployment and consent</h2>
      <p>
        The agent is deployed by the organisation that owns or controls the device. That
        organisation is responsible for giving its personnel the notice, and obtaining any
        consent, that applicable law requires. See the{" "}
        <a href="/privacy/">Privacy Policy</a> for what is collected.
      </p>

      <h2>5. Automatic updates</h2>
      <p>
        The agent checks for updates periodically and applies them automatically. Updates
        are signed, and the agent verifies the signature against a public key built into
        the installed software before applying anything. An update that does not verify is
        refused. The private signing key is never held by the ASTRA backend, so a
        compromise of our servers cannot push software to your devices.
      </p>

      <h2>6. Restrictions</h2>
      <p>You must not:</p>
      <ul>
        <li>install the agent on any device you do not own or control;</li>
        <li>
          reverse engineer, decompile or modify the agent, except to the extent applicable
          law expressly permits;
        </li>
        <li>
          tamper with the allowlist, the signature verification, or the tier controls;
        </li>
        <li>redistribute, sublicense, rent or resell the agent.</li>
      </ul>

      <h2>7. Removal</h2>
      <p>
        The agent can be removed at any time using the supplied uninstaller or standard
        Windows uninstall. Removing it stops all collection from that device.
      </p>

      <h2>8. Ownership</h2>
      <p>
        The agent is licensed, not sold. All intellectual property in it remains with{" "}
        {legal.displayName}.
      </p>

      <h2>9. Warranty and liability</h2>
      <CounselTodo>
        To be drafted by counsel. This section must specifically address liability for the
        effects of a remediation action executed on a customer device, and for a defective
        agent release distributed through the automatic update channel. Those are the two
        ways this software can cause loss, and they should be addressed by name rather
        than left to a general disclaimer. Align the position with the{" "}
        <a href="/terms/">Terms of Service</a> and with the professional indemnity cover
        actually held.
      </CounselTodo>

      <h2>10. Governing law</h2>
      <CounselTodo>
        To match the governing-law clause settled in the Terms of Service.
      </CounselTodo>

      <h2>11. Contact</h2>
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
