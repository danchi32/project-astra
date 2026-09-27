import type { Metadata } from "next";
import {
  ArrowRight,
  BadgeCheck,
  Boxes,
  Building2,
  CheckCircle2,
  Chrome,
  Clock,
  Download,
  EyeOff,
  FileClock,
  FileSpreadsheet,
  Fingerprint,
  Globe,
  KeyRound,
  Layers,
  LockKeyhole,
  LogOut,
  Mail,
  MonitorSmartphone,
  Network,
  Puzzle,
  RefreshCcw,
  ScrollText,
  ShieldAlert,
  ShieldCheck,
  Timer,
  UserPlus,
  UsersRound,
} from "lucide-react";
import { Badge, Button, Container, Section, SectionHeading } from "@/components/ui";
import {
  GroupAccess,
  LoginReport,
  MaskedFill,
  OneTimeCodes,
  PolicyPanel,
  VaultDashboard,
} from "@/components/vault-visuals";
import { bookDemo, site } from "@/lib/site";

const vaultUrl = "https://vault.technomateai.com";

export const metadata: Metadata = {
  title: "Secure Vault — shared portal logins nobody has to see",
  description:
    "Secure Vault stores your team's staffing and vendor portal logins encrypted, assigns them by group, fills them through a browser extension without ever showing them, and records every sign-in.",
  keywords: [
    "shared password manager for teams",
    "portal credential management",
    "staffing portal logins",
    "enterprise password vault",
    "credential autofill extension",
    "VMS portal access control",
  ],
  alternates: { canonical: "/vault/" },
};

const problems = [
  {
    icon: ShieldAlert,
    title: "The password travels",
    body: "Spreadsheets, chat threads, forwarded emails. Every copy is one more place it can leak from, and none can be taken back.",
  },
  {
    icon: LogOut,
    title: "Leavers keep their access",
    body: "The password is still in their head. Rotating it means changing every portal by hand and telling everyone who still needs it.",
  },
  {
    icon: FileClock,
    title: "Nobody can say who signed in",
    body: "A shared login answers to everyone and to no one. When a portal asks who made a change, you have no record that can answer.",
  },
];

const steps = [
  {
    icon: Boxes,
    title: "Add the portal once",
    body: "URL, username, password — plus a tenant code and a one-time-code method if the portal asks. Everything sensitive is encrypted before storage. Import a spreadsheet if there are many.",
  },
  {
    icon: UsersRound,
    title: "Assign who may use it",
    body: "Assign by group, or straight to a person. Changes take effect at once — nothing to redistribute, nothing to rotate when somebody leaves.",
  },
  {
    icon: Puzzle,
    title: "They click, the extension signs in",
    body: "They open it from their dashboard. The extension fills and submits behind a cover screen, handling the one-time code. The credential reaches the portal and nothing else.",
  },
];

const neverSeen = [
  "Fields are masked as they are filled, and stay masked afterwards",
  "There is no reveal control — not in the dashboard, not in the extension",
  "Copying out of a protected field is blocked",
  "A portal's own show-password toggle is intercepted and reversed",
  "A cover screen hides the sign-in while it happens",
  "If that cover screen ends early, the credentials underneath stay unreadable",
  "The browser's own offer to save the password is held off over your portals",
  "Usernames are shortened wherever they are listed, never shown whole",
];

const features = [
  { icon: Boxes, title: "Portal catalogue", body: "Every portal you use, credentials encrypted at rest. Added one at a time or imported." },
  { icon: Layers, title: "Groups and access", body: "Group portals and people, then assign in bulk from either list. A portal with no group stays a direct login." },
  { icon: Puzzle, title: "Browser extension", body: "Chrome, Edge, Brave and Opera from a packaged build; Firefox installs in one click and updates itself." },
  { icon: Fingerprint, title: "Authenticator codes", body: "Store the TOTP secret and the extension generates the code at sign-in. Nobody reaches for a phone." },
  { icon: Mail, title: "Codes sent by email", body: "Point the vault at a mailbox over IMAP and it reads the emailed code out and enters it." },
  { icon: KeyRound, title: "Microsoft Entra ID SSO", body: "Sign in with a Microsoft work account. Entra proves who they are; the vault decides what they may open." },
  { icon: ShieldCheck, title: "Enforced MFA", body: "Require Microsoft sign-in, and password sign-in is refused for that organization." },
  { icon: Network, title: "IP allow and block rules", body: "Restrict by network — per organization, group or person. Applies to passwords, SSO, the API and pairing alike." },
  { icon: MonitorSmartphone, title: "One browser at a time", body: "A new sign-in ends the previous session; a new pairing revokes the old one. Access follows the person, not a machine." },
  { icon: Timer, title: "Session and idle limits", body: "How long a sign-in lasts, how long a browser stays trusted, how long an open portal may sit idle." },
  { icon: RefreshCcw, title: "Walk-away protection", body: "Cookies, local storage and indexed databases are cleared when a portal session ends — not just the cookie." },
  { icon: ScrollText, title: "Audit timeline", body: "Sign-ins, launches, reveals, policy and access changes, recorded as they happen." },
  { icon: Download, title: "Login report", body: "Who opened what, from which IP and browser, and when. Filterable, and exportable as CSV." },
  { icon: FileSpreadsheet, title: "Bulk import", body: "Users from CSV, portals from Excel or CSV, with a per-row report of anything that failed." },
  { icon: UserPlus, title: "Self-service password change", body: "People change their own password, and every other browser is signed out the moment they do." },
  { icon: Building2, title: "Your branding", body: "Your logo across the dashboard and admin console." },
  { icon: BadgeCheck, title: "Licences and validity", body: "Seat counts and a validity date enforced at sign-in, so access stops when an agreement does." },
  { icon: Globe, title: "Single sign-on portals", body: "Name the identity host a portal hands off to, and the vault follows it through the redirect." },
];

const encryption = [
  {
    title: "Your organization's portal catalogue",
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

const controls = [
  "Session cookies are HttpOnly, Secure and SameSite-Strict",
  "Credentials are released only to an authorised, paired browser",
  "Every administrator action is recorded against the organization it affected",
  "Revealing a stored credential in the admin console is time-limited and audited",
  "Deactivating a person signs them out of every browser and extension at once",
  "Suspending an organization stops its people signing in without deleting anything",
];

export default function VaultPage() {
  return (
    <>
      <section className="aurora grain relative -mt-16 overflow-hidden pb-16 pt-28 sm:pt-36">
        <Container>
          <div className="grid gap-12 lg:grid-cols-[1.05fr_0.95fr] lg:items-center">
          <div className="max-w-3xl">
            <Badge>
              <LockKeyhole className="h-3.5 w-3.5 text-brand-500" /> Secure Vault
            </Badge>
            <h1 className="mt-5 text-4xl font-extrabold leading-tight tracking-tight sm:text-5xl">
              Your team signs in once. They never see the password.
            </h1>
            <p className="mt-6 max-w-2xl text-lg leading-relaxed text-secondary-token">
              Shared portal logins end up in spreadsheets. Secure Vault keeps them
              encrypted, hands them out by group, and fills them in through a browser
              extension — masked the whole way, and recorded every time.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Button href={vaultUrl} external>
                Open the vault <ArrowRight className="h-4 w-4" />
              </Button>
              <Button href={bookDemo.href} external={bookDemo.external} variant="secondary">
                Book a walkthrough
              </Button>
            </div>
            <p className="mt-5 text-sm text-secondary-token">
              Built by {site.company}.
            </p>
          </div>
          <VaultDashboard />
          </div>
        </Container>
      </section>

      <Section>
        <Container>
          <SectionHeading
            eyebrow="Why it exists"
            title="A shared login is a password with no owner"
            subtitle="The moment a credential is typed by more than one person, three problems arrive together."
          />
          <div className="mt-14 grid gap-6 md:grid-cols-3">
            {problems.map((item) => (
              <div key={item.title} className="rounded-2xl border border-token bg-surface p-7">
                <item.icon className="h-6 w-6 text-brand-500" />
                <h3 className="mt-4 text-lg font-semibold">{item.title}</h3>
                <p className="mt-3 text-sm leading-relaxed text-secondary-token">{item.body}</p>
              </div>
            ))}
          </div>
        </Container>
      </Section>

      <Section className="border-y border-token bg-surface/50">
        <Container>
          <SectionHeading
            eyebrow="How it works"
            title="Three steps, and nobody learns a password"
            subtitle="Set a portal up once. After that, access is granted and withdrawn — never sent."
          />
          <div className="mt-14 grid gap-6 md:grid-cols-3">
            {steps.map((step, index) => (
              <div key={step.title} className="relative rounded-2xl border border-token bg-surface p-7">
                <span className="text-sm font-semibold text-brand-500">Step {index + 1}</span>
                <step.icon className="mt-4 h-6 w-6 text-brand-500" />
                <h3 className="mt-4 text-lg font-semibold">{step.title}</h3>
                <p className="mt-3 text-sm leading-relaxed text-secondary-token">{step.body}</p>
              </div>
            ))}
          </div>
          <div className="mx-auto mt-12 max-w-3xl">
            <OneTimeCodes />
          </div>
        </Container>
      </Section>

      <Section>
        <Container>
          <div className="grid gap-12 lg:grid-cols-2 lg:items-start">
            <div>
              <Badge>
                <EyeOff className="h-3.5 w-3.5 text-brand-500" /> Non-revealing by design
              </Badge>
              <h2 className="mt-5 text-3xl font-bold tracking-tight sm:text-4xl">
                Filled in front of them, and still unreadable
              </h2>
              <p className="mt-5 text-base leading-relaxed text-secondary-token">
                Most password managers hide a credential until somebody presses the eye icon.
                This one has no eye icon. A credential can be used by someone who could not
                repeat it if they were asked. When an administrator genuinely needs to read one,
                that reveal is time-limited and audited.
              </p>
            </div>
            <MaskedFill />
          </div>
          <ul className="mx-auto mt-12 grid max-w-5xl gap-3 sm:grid-cols-2">
            {neverSeen.map((line) => (
              <li key={line} className="flex items-start gap-3 rounded-xl border border-token bg-surface px-4 py-3">
                <CheckCircle2 className="mt-0.5 h-4 w-4 flex-none text-brand-500" />
                <span className="text-sm leading-relaxed text-secondary-token">{line}</span>
              </li>
            ))}
          </ul>
        </Container>
      </Section>

      <Section className="border-y border-token bg-surface/50">
        <Container>
          <SectionHeading
            eyebrow="Everything in the box"
            title="What Secure Vault does"
            subtitle="The credentials, the people who may use them, the rules around both, and the record of what happened."
          />
          <div className="mt-14 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {features.map((feature) => (
              <div key={feature.title} className="rounded-2xl border border-token bg-surface p-6">
                <feature.icon className="h-5 w-5 text-brand-500" />
                <h3 className="mt-4 text-base font-semibold">{feature.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-secondary-token">{feature.body}</p>
              </div>
            ))}
          </div>
          <div className="mt-14 grid gap-6 lg:grid-cols-2">
            <GroupAccess />
            <LoginReport />
          </div>
        </Container>
      </Section>

      <Section>
        <Container>
          <SectionHeading
            eyebrow="How credentials are stored"
            title="Encryption, described honestly"
            subtitle="Three things, protected three ways. The differences matter more than the word encrypted."
          />
          <div className="mx-auto mt-14 grid max-w-4xl gap-6">
            {encryption.map((block) => (
              <div key={block.title} className="rounded-2xl border border-token bg-surface p-7">
                <h3 className="text-lg font-semibold">{block.title}</h3>
                <p className="mt-3 text-sm leading-relaxed text-secondary-token">{block.body}</p>
                {block.caveat && (
                  <p className="mt-4 rounded-xl border border-brand-500/25 bg-brand-500/5 px-4 py-3 text-sm leading-relaxed text-secondary-token">
                    {block.caveat}
                  </p>
                )}
              </div>
            ))}
          </div>
        </Container>
      </Section>

      <Section className="border-y border-token bg-surface/50">
        <Container>
          <div className="grid gap-12 lg:grid-cols-2 lg:items-start">
            <div>
              <Badge>
                <ShieldCheck className="h-3.5 w-3.5 text-brand-500" /> Controls
              </Badge>
              <h2 className="mt-5 text-3xl font-bold tracking-tight sm:text-4xl">
                Access you can withdraw as fast as you granted it
              </h2>
              <p className="mt-5 text-base leading-relaxed text-secondary-token">
                Nobody knows the portal password, so withdrawing access is one change in the
                vault rather than a rotation across every portal. Removing a person from a
                group is immediate; so is deactivating them entirely.
              </p>
              <div className="mt-8">
                <Button href={`mailto:${site.contact.security}`} variant="secondary" external>
                  Ask our security team a question
                </Button>
              </div>
            </div>
            <div className="grid gap-6">
              <PolicyPanel />
            <ul className="grid gap-3">
              {controls.map((line) => (
                <li key={line} className="flex items-start gap-3 rounded-xl border border-token bg-surface px-4 py-3">
                  <CheckCircle2 className="mt-0.5 h-4 w-4 flex-none text-brand-500" />
                  <span className="text-sm leading-relaxed text-secondary-token">{line}</span>
                </li>
              ))}
            </ul>
            </div>
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
            Each person connects their browser once. A new pairing ends the previous one, so
            access never quietly accumulates across machines.
          </p>
        </Container>
      </Section>

      <Section className="border-t border-token">
        <Container>
          <div className="mx-auto max-w-3xl rounded-3xl border border-token bg-surface p-10 text-center sm:p-14">
            <Clock className="mx-auto h-7 w-7 text-brand-500" />
            <h2 className="mt-5 text-3xl font-bold tracking-tight sm:text-4xl">
              Stop sending passwords around
            </h2>
            <p className="mx-auto mt-5 max-w-xl text-base leading-relaxed text-secondary-token">
              We will set up your portals, import your people, and show you the audit trail on
              your own data.
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
