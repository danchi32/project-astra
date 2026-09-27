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
    body: "Portal logins get shared in spreadsheets, chat threads and forwarded emails. Every copy is one more place it can leak from, and none of them can be taken back.",
  },
  {
    icon: LogOut,
    title: "Leavers keep their access",
    body: "When someone moves on, the password is still in their head. Rotating it means finding every portal, changing it by hand, and telling everyone who still needs it.",
  },
  {
    icon: FileClock,
    title: "Nobody can say who signed in",
    body: "A shared login answers to everyone and to no one. When a portal asks who made a change, there is no record on your side that can tell them.",
  },
];

const steps = [
  {
    icon: Boxes,
    title: "Add the portal once",
    body: "An administrator saves the login URL, username and password — plus an organization or tenant code and a one-time-code method if the portal asks for them. Everything sensitive is encrypted before it is stored. Bulk-import a spreadsheet if you are starting with many.",
  },
  {
    icon: UsersRound,
    title: "Assign who may use it",
    body: "Put portals into groups and people into groups, or assign a portal straight to a person. Access changes take effect immediately — there is no password to redistribute and nothing to rotate when somebody leaves.",
  },
  {
    icon: Puzzle,
    title: "They click, the extension signs in",
    body: "The person opens the portal from their dashboard. The browser extension fills the form and submits it behind a cover screen, handling the one-time code if there is one. The credential reaches the portal and nothing else.",
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
  { icon: Boxes, title: "Portal catalogue", body: "Every portal your organization uses, with its credentials encrypted at rest. Add them one at a time or import a spreadsheet." },
  { icon: Layers, title: "Groups and access", body: "Group portals and people, then assign in bulk from the user list or the catalogue. A portal with no group stays a direct login." },
  { icon: Puzzle, title: "Browser extension", body: "Chrome, Edge, Brave and Opera from a signed package; Firefox installs in one click and updates itself; a Safari build is produced from the same source." },
  { icon: Fingerprint, title: "Authenticator codes", body: "Store a portal's TOTP secret and the extension generates the six-digit code at sign-in, so nobody has to reach for a phone." },
  { icon: Mail, title: "Codes sent by email", body: "For portals that email a one-time code, point the vault at a mailbox over IMAP and it reads the code out and enters it." },
  { icon: KeyRound, title: "Microsoft Entra ID SSO", body: "Let people sign in with their Microsoft work account, configured per organization. Entra proves who they are; the vault decides what they may open." },
  { icon: ShieldCheck, title: "Enforced MFA", body: "Require Microsoft sign-in for an organization and password sign-in is refused for everyone in it." },
  { icon: Network, title: "IP allow and block rules", body: "Restrict access by network, for the whole organization, a single group, or one person. The rules apply to passwords, SSO, the API and extension pairing alike." },
  { icon: MonitorSmartphone, title: "One browser at a time", body: "A new sign-in ends the previous web session; pairing a new browser revokes the previously paired one. Access follows the person, not a machine they used once." },
  { icon: Timer, title: "Session and idle limits", body: "Set how long a sign-in lasts, how long a paired browser stays trusted, and how long an open portal may sit idle before it is closed out." },
  { icon: RefreshCcw, title: "Walk-away protection", body: "When a portal session ends, cookies, local storage and indexed databases for that site are cleared — not just the cookie, which is what leaves the next person signed in." },
  { icon: ScrollText, title: "Audit timeline", body: "Sign-ins, portal launches, credential reveals, policy changes and access changes, recorded per organization as they happen." },
  { icon: Download, title: "Login report", body: "Who opened which portal, from which IP, on which browser, and when — filterable by person, portal and date, and exportable as CSV." },
  { icon: FileSpreadsheet, title: "Bulk import", body: "Users from CSV and portals from Excel or CSV, in batches, with a per-row report of anything that did not go in." },
  { icon: UserPlus, title: "Self-service password change", body: "People change their own sign-in password without an administrator, and every other browser is signed out the moment they do." },
  { icon: Building2, title: "Your branding", body: "Upload your logo and it appears across the dashboard and admin console for everyone in your organization." },
  { icon: BadgeCheck, title: "Licences and validity", body: "Seat counts and an organization validity date are enforced at sign-in, so access stops when an agreement does." },
  { icon: Globe, title: "Single sign-on portals", body: "Name the identity host a portal hands off to and the vault recognises it there too, instead of losing the login at the redirect." },
];

const encryption = [
  {
    title: "Your organization's portal catalogue",
    body: "Each portal payload is encrypted with AES-256-GCM under a data key belonging to your organization alone, and that key is itself wrapped by the deployment master key. A leaked master key on its own opens nothing — each tenant's wrapped key is needed too.",
    caveat:
      "Stated plainly: because the service unwraps those keys to fill a portal for you, this managed catalogue is not zero-knowledge. Anyone with both the master key and database access could read it. That is the trade for credentials that can be filled without anybody knowing them.",
  },
  {
    title: "A person's own vault",
    body: "Personal entries are encrypted in the browser under a master password that is never stored and never sent to the server. The key is derived with PBKDF2 at 600,000 iterations, and the server holds only ciphertext it cannot read.",
    caveat: null,
  },
  {
    title: "Account sign-in passwords",
    body: "Vault account passwords are hashed with scrypt at a deliberately high work factor and are never recoverable — not by an administrator, and not by us. Repeated wrong attempts on an account are throttled without locking out a whole office behind one shared address.",
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
          <div className="max-w-3xl">
            <Badge>
              <LockKeyhole className="h-3.5 w-3.5 text-brand-500" /> Secure Vault
            </Badge>
            <h1 className="mt-5 text-4xl font-extrabold leading-tight tracking-tight sm:text-5xl">
              Your team signs in once. They never see the password.
            </h1>
            <p className="mt-6 max-w-2xl text-lg leading-relaxed text-secondary-token">
              Staffing, vendor and client portals are shared by whole teams, and the login
              usually ends up in a spreadsheet. Secure Vault keeps those credentials
              encrypted, hands them out by group, and fills them into the portal through a
              browser extension — masked the whole way, and recorded every time.
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
              Built by {site.company} for teams who share portal access and cannot share the password.
            </p>
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
            subtitle="Set a portal up once. After that, access is something you grant and withdraw rather than something you send."
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
                This one has no eye icon. The password goes from encrypted storage into the
                portal&apos;s form and is masked at every point a person could look at it — so
                a credential can be used by someone who could not repeat it if they were asked.
              </p>
              <p className="mt-4 text-base leading-relaxed text-secondary-token">
                When an administrator genuinely needs to read a stored credential, that reveal is
                time-limited and written to the audit log.
              </p>
            </div>
            <ul className="grid gap-3">
              {neverSeen.map((line) => (
                <li key={line} className="flex items-start gap-3 rounded-xl border border-token bg-surface px-4 py-3">
                  <CheckCircle2 className="mt-0.5 h-4 w-4 flex-none text-brand-500" />
                  <span className="text-sm leading-relaxed text-secondary-token">{line}</span>
                </li>
              ))}
            </ul>
          </div>
        </Container>
      </Section>

      <Section className="border-y border-token bg-surface/50">
        <Container>
          <SectionHeading
            eyebrow="Everything in the box"
            title="What Secure Vault does"
            subtitle="One place for the credentials, the people who may use them, the rules around both, and the record of what happened."
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
        </Container>
      </Section>

      <Section>
        <Container>
          <SectionHeading
            eyebrow="How credentials are stored"
            title="Encryption, described honestly"
            subtitle="Three different things are protected three different ways, and the differences matter more than the word encrypted."
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
                Because nobody knows the portal password, taking access away is a change in the
                vault rather than a rotation across every portal and a message to everyone who
                still needs in. Removing a person from a group is immediate, and so is
                deactivating them entirely.
              </p>
              <div className="mt-8">
                <Button href={`mailto:${site.contact.security}`} variant="secondary" external>
                  Ask our security team a question
                </Button>
              </div>
            </div>
            <ul className="grid gap-3">
              {controls.map((line) => (
                <li key={line} className="flex items-start gap-3 rounded-xl border border-token bg-surface px-4 py-3">
                  <CheckCircle2 className="mt-0.5 h-4 w-4 flex-none text-brand-500" />
                  <span className="text-sm leading-relaxed text-secondary-token">{line}</span>
                </li>
              ))}
            </ul>
          </div>
        </Container>
      </Section>

      <Section>
        <Container>
          <SectionHeading
            eyebrow="Browsers"
            title="Wherever your team already works"
            subtitle="One codebase, a dedicated build per browser, and each one installed the way that browser expects."
          />
          <div className="mx-auto mt-14 grid max-w-4xl gap-6 md:grid-cols-3">
            <div className="rounded-2xl border border-token bg-surface p-7">
              <Chrome className="h-6 w-6 text-brand-500" />
              <h3 className="mt-4 text-lg font-semibold">Chrome, Edge, Brave, Opera</h3>
              <p className="mt-3 text-sm leading-relaxed text-secondary-token">
                A packaged build downloaded from your vault and loaded from the browser&apos;s
                extensions page.
              </p>
            </div>
            <div className="rounded-2xl border border-token bg-surface p-7">
              <Globe className="h-6 w-6 text-brand-500" />
              <h3 className="mt-4 text-lg font-semibold">Firefox</h3>
              <p className="mt-3 text-sm leading-relaxed text-secondary-token">
                Signed by Mozilla, so it installs in a single click and then keeps itself up to
                date without anybody reinstalling anything.
              </p>
            </div>
            <div className="rounded-2xl border border-token bg-surface p-7">
              <MonitorSmartphone className="h-6 w-6 text-brand-500" />
              <h3 className="mt-4 text-lg font-semibold">Safari</h3>
              <p className="mt-3 text-sm leading-relaxed text-secondary-token">
                Built from the same source and packaged as a Safari web extension for macOS.
              </p>
            </div>
          </div>
          <p className="mx-auto mt-8 max-w-2xl text-center text-sm text-secondary-token">
            Each person connects their browser once. Pairing a new one ends the previous
            pairing, so access never quietly accumulates across machines.
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
              your own data. If it does not suit how your team works, you will know inside a
              call.
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
