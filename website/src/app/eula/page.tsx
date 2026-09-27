import type { Metadata } from "next";
import { LegalPage } from "@/components/LegalPage";
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
      effective="2026-09-26"
      reviewed
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

      <h2>3A. Remote support</h2>
      <p>
        If the organisation that enrolled the device has remote support on its plan and
        switched on, the agent installs a separate remote-support service on the device.
        It lets that organisation&rsquo;s technicians ask to view and control the screen
        to help the person using it. Every session:
      </p>
      <ul>
        <li>
          starts only after the person at the device clicks <strong>Allow</strong> on a
          prompt that names the technician and the reason;
        </li>
        <li>is streamed live and is not recorded;</li>
        <li>
          shares the clipboard both ways, and has file transfer and command-line access
          disabled;
        </li>
        <li>is logged in the organisation&rsquo;s audit trail;</li>
        <li>can be started only by a person, never by ASTRA&rsquo;s AI.</li>
      </ul>
      <p>
        The remote-support service is removed automatically when the feature is switched
        off for the organisation, and with the agent.
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
      <p>
        We warrant that the agent will perform materially as described in this licence
        while your subscription is active. If it does not, we will correct the defect or,
        if we cannot within a reasonable time, you may end your subscription and recover
        the fees paid for the period after the defect was reported. Beyond that, and to
        the extent the law allows, the agent is provided &ldquo;as is&rdquo;.
      </p>
      <p>
        <strong>Remediation actions.</strong> The agent changes a device only through the
        actions in its built-in catalogue and at the tier your organisation configured. We
        are responsible for an action doing what its catalogue entry says; we are not
        responsible for the consequences of an action your organisation approved or
        enabled for automatic approval, where the action did what it describes.
      </p>
      <p>
        <strong>Automatic updates.</strong> If an agent release we publish causes a
        device fault, we will withdraw or correct that release promptly and help you
        restore affected devices at no charge.
      </p>
      <p>
        <strong>Limits.</strong> Our total liability arising out of the agent is subject
        to the limits in section 9 of the <a href="/terms/">Terms of Service</a> &mdash;
        in summary, the fees you paid in the 12 months before the claim, with no liability
        for indirect or consequential loss, loss of data you could have restored from a
        backup, or lost profits. Nothing in this licence limits liability that cannot be
        limited by law, including for fraud.
      </p>

      <h2>10. Governing law</h2>
      <p>
        This licence is governed by the laws of India. Disputes are resolved as set out in
        section 11 of the <a href="/terms/">Terms of Service</a>: by arbitration seated in
        Gautam Budh Nagar, Uttar Pradesh, with the courts there having exclusive
        jurisdiction.
      </p>

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
