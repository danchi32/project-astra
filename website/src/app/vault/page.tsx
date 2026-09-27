import type { Metadata } from "next";
import {
  ArrowRight,
  BadgeCheck,
  Boxes,
  Building2,
  Chrome,
  Download,
  EyeOff,
  FileSpreadsheet,
  Fingerprint,
  Globe,
  HelpCircle,
  KeyRound,
  Layers,
  LockKeyhole,
  Mail,
  MonitorSmartphone,
  Network,
  RefreshCcw,
  ScrollText,
  ShieldCheck,
  Timer,
  UserPlus,
  UsersRound,
} from "lucide-react";
import { Badge, Button, Container, Reveal, Section, SectionHeading } from "@/components/ui";
import { VaultDemo } from "@/components/vault-demo";
import { OnPageSignIn } from "@/components/vault-onpage";
import { WayFromExtension, WayFromVault, WayOnThePage } from "@/components/vault-ways";
import {
  GroupAccess,
  LoginReport,
  MaskedFill,
  OneTimeCodes,
  PolicyPanel,
} from "@/components/vault-visuals";
import { bookDemo, site } from "@/lib/site";

const vaultUrl = "https://vault.technomateai.com";

export const metadata: Metadata = {
  title: "Secure Vault — shared portal logins nobody has to see",
  description:
    "Secure Vault keeps your team's portal logins encrypted, assigns them by group, fills them through a browser extension without showing them, and records every sign-in.",
  keywords: [
    "shared password manager for teams",
    "portal credential management",
    "enterprise password vault",
    "credential autofill extension",
  ],
  alternates: { canonical: "/vault/" },
};

/* One claim per row, each with the panel that shows it happening. */
const rows = [
  {
    eyebrow: "Non-revealing",
    title: "Filled in front of them, still unreadable",
    body: "No eye icon, anywhere. A credential can be used by someone who could not repeat it if they were asked.",
    visual: <MaskedFill />,
  },
  {
    eyebrow: "On the portal's own page",
    title: "They never even opened the vault",
    body: "Reached the portal from their own bookmark? The badge appears in the field, offers the logins that belong to that site, and signs them in there.",
    visual: <OnPageSignIn />,
  },
  {
    eyebrow: "Access",
    title: "Access you grant, not access you send",
    body: "Group portals and people, or assign one straight to a person. Nothing to redistribute, nothing to rotate when somebody leaves.",
    visual: <GroupAccess />,
  },
  {
    eyebrow: "Evidence",
    title: "Every sign-in, on the record",
    body: "Each launch written down with the person, the portal, the address and the browser. Filterable, and exportable.",
    visual: <LoginReport />,
  },
  {
    eyebrow: "One-time codes",
    title: "The second factor, handled for them",
    body: "Authenticator codes from a stored secret, emailed codes read over IMAP. Nobody reaches for a phone.",
    visual: <OneTimeCodes />,
  },
  {
    eyebrow: "Policy",
    title: "Rules you set once",
    body: "Network restrictions, enforced Microsoft sign-in, session lifetimes and idle limits — across the organization, a group, or one person.",
    visual: <PolicyPanel />,
  },
];

const features = [
  { icon: Boxes, title: "Portal catalogue", body: "Every portal you use, credentials encrypted at rest." },
  { icon: Layers, title: "Groups and access", body: "Group portals and people, then assign in bulk." },
  { icon: Fingerprint, title: "Authenticator codes", body: "Generated from the stored secret at sign-in." },
  { icon: Mail, title: "Emailed codes", body: "Read over IMAP from a mailbox you nominate." },
  { icon: KeyRound, title: "Microsoft Entra SSO", body: "Sign in with a Microsoft work account." },
  { icon: ShieldCheck, title: "Enforced MFA", body: "Require Microsoft sign-in for an organization." },
  { icon: Network, title: "IP allow and block", body: "Per organization, group or person." },
  { icon: MonitorSmartphone, title: "One browser at a time", body: "A new pairing revokes the old one." },
  { icon: Timer, title: "Session and idle limits", body: "How long a sign-in and an open portal last." },
  { icon: RefreshCcw, title: "Walk-away protection", body: "Cookies, local storage and databases cleared." },
  { icon: ScrollText, title: "Audit timeline", body: "Recorded per organization as it happens." },
  { icon: Download, title: "Login report", body: "Filterable, and exportable as CSV." },
  { icon: FileSpreadsheet, title: "Bulk import", body: "Users from CSV, portals from Excel." },
  { icon: UserPlus, title: "Self-service password", body: "Changed without an administrator." },
  { icon: Building2, title: "Your branding", body: "Your logo across dashboard and console." },
  { icon: BadgeCheck, title: "Licences and validity", body: "Seats and dates enforced at sign-in." },
  { icon: Globe, title: "SSO portals", body: "Followed through the identity redirect." },
  { icon: EyeOff, title: "Audited reveals", body: "Time-limited, and written to the log." },
];

const encryption = [
  {
    title: "Your organization's catalogue",
    body: "AES-256-GCM under a data key belonging to your organization alone, itself wrapped by the deployment master key. A leaked master key opens nothing on its own.",
    caveat:
      "Stated plainly: because the service unwraps those keys to fill a portal for you, this catalogue is not zero-knowledge. That is the trade for credentials nobody has to know.",
  },
  {
    title: "A person's own vault",
    body: "Encrypted in the browser under a master password that is never stored or sent. PBKDF2 at 600,000 iterations; the server holds ciphertext it cannot read.",
    caveat: null,
  },
  {
    title: "Account sign-in passwords",
    body: "Hashed with scrypt at a high work factor and never recoverable — not by an administrator, not by us. Wrong attempts are throttled per account, not per address.",
    caveat: null,
  },
];

const faqs = [
  {
    q: "Can our people see the portal passwords?",
    a: "No. There is no reveal control in the dashboard or the extension, fields stay masked after they are filled, and copying out of them is blocked. An administrator can reveal a stored credential when they genuinely need to; that reveal is time-limited and written to the audit log.",
  },
  {
    q: "What happens when somebody leaves?",
    a: "You remove them, or deactivate them. Every browser and paired extension they used is signed out at once. Nothing has to be rotated, because they never knew the password.",
  },
  {
    q: "Does it work with portals that ask for a code?",
    a: "Yes, both kinds. Authenticator codes are generated from a secret you store once. Codes sent by email are read from a mailbox you nominate over IMAP, and entered automatically.",
  },
  {
    q: "Which browsers are supported?",
    a: "Chrome, Edge, Brave and Opera install a packaged build from your own vault. Firefox installs in one click from a Mozilla-signed build and keeps itself up to date.",
  },
  {
    q: "Can we restrict where people sign in from?",
    a: "Yes. Allow and block rules by network apply to password sign-in, Microsoft SSO, the API and extension pairing alike, and can be set for the whole organization, one group, or one person.",
  },
  {
    q: "Is it zero-knowledge?",
    a: "A person's own vault is: it is encrypted in their browser and the server cannot read it. The shared organization catalogue is not, because the service has to unwrap those keys to fill a portal on someone's behalf. We would rather say so than let you find out later.",
  },
];

export default function VaultPage() {
  return (
    <>
      {/* The product plays itself rather than being described first. */}
      <section className="aurora grain relative -mt-16 overflow-hidden pb-20 pt-28 sm:pt-36">
        <Container>
          <div className="grid gap-12 lg:grid-cols-2 lg:items-center">
            <div>
              <Badge>
                <LockKeyhole className="h-3.5 w-3.5 text-brand-500" /> Secure Vault
              </Badge>
              <h1 className="mt-5 text-4xl font-extrabold leading-tight tracking-tight sm:text-5xl">
                Your team signs in once. They never see the password.
              </h1>
              <p className="mt-6 max-w-xl text-lg leading-relaxed text-secondary-token">
                Shared portal logins end up in spreadsheets. Secure Vault keeps them encrypted,
                hands them out by group, and fills them in through a browser extension — masked
                the whole way, and recorded every time.
              </p>
              <div className="mt-8 flex flex-wrap gap-3">
                <Button href={vaultUrl} external>
                  Open the vault <ArrowRight className="h-4 w-4" />
                </Button>
                <Button href={bookDemo.href} external={bookDemo.external} variant="secondary">
                  Book a walkthrough
                </Button>
              </div>
              <p className="mt-5 text-sm text-secondary-token">Built by {site.company}.</p>
            </div>
            <VaultDemo />
          </div>
        </Container>
      </section>

      {/* Three entry points, because the answer to "how much has to change for us" is none. */}
      <Section className="border-y border-token bg-surface/50">
        <Container>
          <SectionHeading
            eyebrow="Three ways in"
            title="However they reach the portal"
            subtitle="The same credential, the same masking and the same record, whichever door they come through."
          />
          <div className="mt-14 grid gap-6 lg:grid-cols-3">
            <Reveal><WayFromVault /></Reveal>
            <Reveal delay={0.1}><WayFromExtension /></Reveal>
            <Reveal delay={0.2}><WayOnThePage /></Reveal>
          </div>
        </Container>
      </Section>

      {rows.map((entry, index) => (
        <Section key={entry.title} className={index % 2 === 0 ? "" : "border-y border-token bg-surface/50"}>
          <Container>
            <div className="grid gap-12 lg:grid-cols-2 lg:items-center">
              <Reveal className={index % 2 === 1 ? "lg:order-2" : ""}>
                <span className="text-sm font-semibold uppercase tracking-wider text-brand-500">{entry.eyebrow}</span>
                <h2 className="mt-3 text-3xl font-bold tracking-tight sm:text-4xl">{entry.title}</h2>
                <p className="mt-5 text-base leading-relaxed text-secondary-token">{entry.body}</p>
              </Reveal>
              <Reveal delay={0.1} className={index % 2 === 1 ? "lg:order-1" : ""}>
                {entry.visual}
              </Reveal>
            </div>
          </Container>
        </Section>
      ))}

      <Section className="border-t border-token">
        <Container>
          <SectionHeading
            eyebrow="Everything in the box"
            title="What Secure Vault does"
            subtitle="The credentials, the people who may use them, the rules around both, and the record of what happened."
          />
          <div className="mt-14 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {features.map((feature) => (
              <div key={feature.title} className="rounded-2xl border border-token bg-surface p-5">
                <feature.icon className="h-5 w-5 text-brand-500" />
                <h3 className="mt-3 text-sm font-semibold">{feature.title}</h3>
                <p className="mt-1.5 text-xs leading-relaxed text-secondary-token">{feature.body}</p>
              </div>
            ))}
          </div>
        </Container>
      </Section>

      <Section className="border-y border-token bg-surface/50">
        <Container>
          <SectionHeading
            eyebrow="How credentials are stored"
            title="Encryption, described honestly"
            subtitle="Three things, protected three ways. The differences matter more than the word encrypted."
          />
          <div className="mx-auto mt-14 grid max-w-4xl gap-6">
            {encryption.map((block) => (
              <Reveal key={block.title}>
                <div className="rounded-2xl border border-token bg-surface p-7">
                  <h3 className="text-lg font-semibold">{block.title}</h3>
                  <p className="mt-3 text-sm leading-relaxed text-secondary-token">{block.body}</p>
                  {block.caveat && (
                    <p className="mt-4 rounded-xl border border-brand-500/25 bg-brand-500/5 px-4 py-3 text-sm leading-relaxed text-secondary-token">
                      {block.caveat}
                    </p>
                  )}
                </div>
              </Reveal>
            ))}
          </div>
        </Container>
      </Section>

      <Section>
        <Container>
          <SectionHeading
            eyebrow="Browsers"
            title="Wherever your team already works"
            subtitle="One codebase, a build per browser, each installed the way that browser expects."
          />
          <div className="mx-auto mt-14 grid max-w-3xl gap-6 md:grid-cols-2">
            <div className="rounded-2xl border border-token bg-surface p-7">
              <Chrome className="h-6 w-6 text-brand-500" />
              <h3 className="mt-4 text-lg font-semibold">Chrome, Edge, Brave, Opera</h3>
              <p className="mt-3 text-sm leading-relaxed text-secondary-token">
                A packaged build downloaded from your vault and loaded from the extensions page.
              </p>
            </div>
            <div className="rounded-2xl border border-token bg-surface p-7">
              <Globe className="h-6 w-6 text-brand-500" />
              <h3 className="mt-4 text-lg font-semibold">Firefox</h3>
              <p className="mt-3 text-sm leading-relaxed text-secondary-token">
                Signed by Mozilla, so it installs in one click and keeps itself up to date.
              </p>
            </div>
          </div>
          <p className="mx-auto mt-8 max-w-2xl text-center text-sm text-secondary-token">
            Each person connects their browser once. A new pairing ends the previous one, so access
            never quietly accumulates across machines.
          </p>
        </Container>
      </Section>

      <Section className="border-y border-token bg-surface/50">
        <Container>
          <SectionHeading eyebrow="FAQ" title="Questions, answered" />
          <div className="mx-auto mt-12 max-w-3xl space-y-4">
            {faqs.map((faq, index) => (
              <Reveal key={faq.q} delay={index * 0.06}>
                <div className="rounded-2xl border border-token bg-surface p-6">
                  <h3 className="flex items-start gap-2 text-base font-semibold">
                    <HelpCircle className="mt-0.5 h-5 w-5 flex-none text-brand-500" />
                    {faq.q}
                  </h3>
                  <p className="mt-2 pl-7 text-sm leading-relaxed text-secondary-token">{faq.a}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </Container>
      </Section>

      <Section>
        <Container>
          <div className="mx-auto max-w-3xl rounded-3xl border border-token bg-surface p-10 text-center sm:p-14">
            <UsersRound className="mx-auto h-7 w-7 text-brand-500" />
            <h2 className="mt-5 text-3xl font-bold tracking-tight sm:text-4xl">
              Stop sending passwords around
            </h2>
            <p className="mx-auto mt-5 max-w-xl text-base leading-relaxed text-secondary-token">
              We will set up your portals, import your people, and show you the audit trail on your
              own data.
            </p>
            <div className="mt-8 flex flex-wrap justify-center gap-3">
              <Button href={bookDemo.href} external={bookDemo.external}>
                Book a walkthrough <ArrowRight className="h-4 w-4" />
              </Button>
              <Button href="/contact" variant="secondary">
                Talk to us
              </Button>
            </div>
          </div>
        </Container>
      </Section>
    </>
  );
}
