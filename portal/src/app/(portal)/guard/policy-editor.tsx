"use client";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Building2, Globe, KeyRound, ShieldCheck, Trash2, Usb, Users } from "lucide-react";
import {
  FINDING_KINDS, SAVIO_EXTENSION_ID, downloadExtension, getDrivesSeen, getSiteCategories,
  type BrowserPolicy, type ExceptionBody, type FindingKind,
} from "@/lib/api/guard";
import { listUserTeams } from "@/lib/api/grouping";
import { listAllUsers } from "@/lib/api/users";
import { SearchableSelect } from "@/components/searchable-select";
import { apiErrorMessage } from "@/lib/utils";
import { Card, Chip, Choice, Lines, Setting, Toggle, button, field, muted, tint } from "./policy-ui";

// One browser policy's settings, the default one or a named one, in sections like a DLP console.
// The page saves it: this component only edits the draft.

export interface Draft {
  // "full": a whole policy (the default one or a named one). "exception": only some modules,
  // laid over whatever full policy the person gets.
  kind: "full" | "exception";
  form: BrowserPolicy;
  exception: ExceptionBody;
  // An exception's Google sign-in: left alone, personal Gmail allowed, or company accounts only.
  gmail: "leave" | "personal" | "company";
  name: string;
  priority: number;
  team_ids: string[];
  user_ids: string[];
  // The lists typed one per line, kept as text while editing.
  text: Record<TextKey, string>;
}
type TextKey = "blocked" | "allowed" | "google" | "watched" | "keywords" | "claude" | "chatgpt" | "slack" | "extensions"
  | "xallow" | "xblock" | "xgoogle";

export const lines = (s: string) => s.split(/[\n,]/).map((x) => x.trim()).filter(Boolean);

export function draftOf(policy: BrowserPolicy, meta?: { name: string; priority: number; team_ids: string[]; user_ids: string[] },
                        exception?: ExceptionBody | null): Draft {
  const x = exception ?? {};
  const google = x.google_allowed_domains;
  return {
    kind: exception ? "exception" : "full", form: policy, exception: x,
    gmail: google == null ? "leave" : google.length ? "company" : "personal",
    name: meta?.name ?? "", priority: meta?.priority ?? 10,
    team_ids: meta?.team_ids ?? [], user_ids: meta?.user_ids ?? [],
    text: { blocked: policy.blocked_sites.join("\n"), allowed: policy.allowed_sites.join("\n"),
            google: policy.google_allowed_domains.join("\n"), watched: policy.guard_watched_sites.join("\n"),
            keywords: policy.guard_keywords.join("\n"), claude: policy.claude_org_ids.join("\n"),
            chatgpt: policy.chatgpt_workspace_ids.join("\n"), slack: policy.slack_allowed_ids.join("\n"),
            extensions: (policy.extension_allowlist ?? []).join("\n"),
            xallow: (x.allow_sites ?? []).join("\n"), xblock: (x.block_sites ?? []).join("\n"),
            xgoogle: (google ?? []).join("\n") },
  };
}

/** An exception as the API takes it: only what it changes. */
export function exceptionOf(d: Draft): ExceptionBody {
  const t = d.text;
  return { ...d.exception, allow_sites: lines(t.xallow), block_sites: lines(t.xblock),
           google_allowed_domains: d.gmail === "leave" ? null : d.gmail === "personal" ? [] : lines(t.xgoogle) };
}

/** What an exception changes, in a few words, for the policy list. */
export function changesOf(x: ExceptionBody): string[] {
  const out: string[] = [];
  if ([x.incognito_off, x.new_profiles_off, x.dev_tools_off, x.block_other_browsers].some((v) => v != null)) out.push("Browser controls");
  if (x.allow_sites?.length || x.allow_categories?.length) out.push("Sites allowed");
  if (x.block_sites?.length || x.block_categories?.length) out.push("Sites blocked");
  if (x.google_allowed_domains != null) out.push(x.google_allowed_domains.length ? "Company Google only" : "Personal Gmail allowed");
  if (x.guard_mode) out.push("Sensitive data mode");
  if (x.usb_mode || x.usb_observe != null) out.push("USB");
  return out;
}

/** The policy as the API takes it: the typed lists turned back into arrays. */
export function policyOf(d: Draft): BrowserPolicy {
  const t = d.text;
  return { ...d.form, blocked_sites: lines(t.blocked), allowed_sites: lines(t.allowed),
           google_allowed_domains: lines(t.google), guard_watched_sites: lines(t.watched),
           // Keywords may contain commas ("Q3, final"): one per line only.
           guard_keywords: t.keywords.split("\n").map((x) => x.trim()).filter(Boolean),
           claude_org_ids: lines(t.claude), chatgpt_workspace_ids: lines(t.chatgpt),
           slack_allowed_ids: lines(t.slack), extension_allowlist: lines(t.extensions) };
}

const SECTIONS = [
  { key: "assign", label: "Assignment", icon: Users, named: true },
  { key: "browser", label: "Browser controls", icon: ShieldCheck },
  { key: "sites", label: "Websites", icon: Globe },
  { key: "data", label: "Sensitive data", icon: KeyRound },
  { key: "accounts", label: "Company accounts", icon: Building2 },
  { key: "usb", label: "USB drives", icon: Usb },
] as const;
type Section = (typeof SECTIONS)[number]["key"];

const SWITCHES: { key: keyof BrowserPolicy; label: string; help: string }[] = [
  { key: "incognito_off", label: "Block private windows", help: "Incognito, InPrivate and Firefox private windows run without the extension." },
  { key: "extension_developer_mode_off", label: "Block extension developer mode", help: "Stops people loading unpacked extensions in Chrome and Edge." },
  { key: "new_profiles_off", label: "Block new profiles and guest windows", help: "A fresh profile would start without the company's settings." },
  { key: "dev_tools_off", label: "Block developer tools", help: "Broader: IT staff can't use them either. Firefox's only way to block temporary add-ons." },
  { key: "block_other_browsers", label: "Close other browsers",
    help: "Brave, Opera, Vivaldi, Yandex, Tor, Chromium, Waterfox and LibreWolf are out of reach of these settings, so SAVIO closes them as they start and tells the person to use Chrome, Edge or Firefox." },
];

const MODES: { value: BrowserPolicy["guard_mode"]; label: string; help: string }[] = [
  { value: "log", label: "Record only", help: "Nothing is stopped. Every organization starts here for 14 days." },
  { value: "warn", label: "Warn", help: "The person is told what was found and can go ahead." },
  { value: "justify", label: "Ask for a reason", help: "To go ahead, the person picks a work reason. You see which." },
  { value: "redact", label: "Hide the sensitive parts", help: "Pastes, form text and text files go ahead with numbers replaced, e.g. [PAN]. Word, Excel and PDF files get a warning." },
  { value: "approve", label: "Needs IT approval", help: "Held until an admin approves it under Approvals." },
  { value: "block", label: "Block", help: "Paste, upload or send is refused. If the check itself fails, it warns instead." },
];

export const USB_MODES: { value: BrowserPolicy["usb_mode"]; label: string; help: string }[] = [
  { value: "off", label: "Leave as they are", help: "SAVIO does not change anything about USB drives." },
  { value: "read_only", label: "Read-only", help: "Files can be opened from a drive or phone, never copied onto one." },
  { value: "encrypted_only", label: "Encrypted drives only", help: "Copying only onto drives encrypted with BitLocker To Go; phones read-only." },
  { value: "on_request", label: "Read-only, IT can allow writing for a while",
    help: "Read-only until IT allows writing on one PC for a set time (under PCs). It ends by itself." },
  { value: "company_drives", label: "Company drives only", help: "Only the drives you approve work; any other USB drive does not work at all. Phones read-only." },
  { value: "block", label: "Block", help: "No access to USB drives or phones at all." },
];

export function PolicyEditor({ draft, setDraft, isDefault, isNew, canEdit, pilotUntil, saving, msg, version, savedAt,
                               onBack, onSave, onDelete }: {
  draft: Draft; setDraft: (d: Draft) => void; isDefault: boolean; isNew: boolean; canEdit: boolean;
  pilotUntil: Date | null; saving: boolean; msg: { ok: boolean; text: string } | null;
  version: number | null; savedAt: string | null;
  onBack: () => void; onSave: () => void; onDelete: () => void;
}) {
  const [section, setSection] = useState<Section>(isDefault ? "browser" : "assign");
  const form = draft.form;
  const setForm = (f: BrowserPolicy) => setDraft({ ...draft, form: f });
  const setText = (k: TextKey, v: string) => setDraft({ ...draft, text: { ...draft.text, [k]: v } });
  const isException = draft.kind === "exception";
  // Company accounts need the extension's IDs, which only a full policy holds.
  const sections = SECTIONS.filter((s) => !(("named" in s) && isDefault) && !(isException && s.key === "accounts"));

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3 min-w-0">
          <button type="button" onClick={onBack} aria-label="All policies" className="p-2 rounded-lg" style={button.plain}>
            <ArrowLeft size={16} />
          </button>
          <div className="min-w-0">
            <div className="text-xs" style={muted}>Browser policies</div>
            <h2 className="text-base font-semibold truncate" style={{ color: "var(--text-primary)" }}>
              {isDefault ? "Default policy" : draft.name || (isException ? "New exception" : "New policy")}
            </h2>
          </div>
          {isDefault && <Chip>Everyone not covered by another policy</Chip>}
          {!isDefault && <Chip tone={isException ? "warn" : "neutral"}>{isException ? "Exception" : "Full policy"}</Chip>}
          {!isDefault && !isNew && <Chip tone="accent">Priority {draft.priority}</Chip>}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs" style={muted}>
            {version ? `Version ${version}` : "Not saved yet"}{savedAt ? ` · saved ${new Date(savedAt).toLocaleString()}` : ""}
            {!canEdit && " · only an admin can change it"}
          </span>
          {canEdit && !isDefault && !isNew && (
            <button type="button" onClick={onDelete} disabled={saving}
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium disabled:opacity-50" style={button.danger}>
              <Trash2 size={14} /> Delete
            </button>
          )}
          {canEdit && (
            <button type="button" onClick={onSave} disabled={saving}
              className="px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-50" style={button.primary}>
              {saving ? "Saving…" : isNew ? (isException ? "Create exception" : "Create policy") : "Save changes"}
            </button>
          )}
        </div>
      </div>
      {msg && (
        <div className="rounded-lg px-4 py-2 text-sm"
          style={{ background: tint(msg.ok ? "var(--health-good)" : "var(--health-bad)"), color: msg.ok ? "var(--health-good)" : "var(--health-bad)" }}>
          {msg.text}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-[13rem_1fr] gap-4 items-start">
        <nav className="flex lg:flex-col gap-1 overflow-x-auto lg:sticky lg:top-4 rounded-xl p-2"
          style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
          {sections.map(({ key, label, icon: Icon }) => (
            <button key={key} type="button" onClick={() => setSection(key)}
              className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm whitespace-nowrap text-left"
              style={section === key
                ? { background: tint("var(--accent)"), color: "var(--accent)", fontWeight: 600 }
                : { color: "var(--text-primary)" }}>
              <Icon size={15} /> {label}
            </button>
          ))}
        </nav>

        <div className="space-y-4 min-w-0">
          {section === "assign" && <Assignment draft={draft} setDraft={setDraft} canEdit={canEdit} />}

          {isException && section !== "assign" && (
            <ExceptionModules section={section} draft={draft} setDraft={setDraft} setText={setText} canEdit={canEdit} pilotUntil={pilotUntil} />
          )}

          {!isException && section === "browser" && (
            <Card title="Browser controls" description="Applied to Chrome, Edge and Firefox, and put back within a minute if someone removes them. A setting your organization already manages another way (Group Policy, Intune) is left alone and shows as a conflict under PCs.">
              {SWITCHES.map((s) => {
                // Loading the extension by hand needs developer mode, so the two can't both be on.
                const handHeld = s.key === "extension_developer_mode_off" && form.extension_install === "manual";
                return (
                  <Setting key={s.key} title={s.label}
                    help={handHeld ? "Off while the SAVIO extension is installed by hand: loading it needs developer mode." : s.help}>
                    <Toggle label={s.label} checked={!!form[s.key]} disabled={!canEdit || handHeld}
                      onChange={(v) => setForm({ ...form, [s.key]: v })} />
                  </Setting>
                );
              })}
            </Card>
          )}

          {!isException && section === "sites" && <Sites draft={draft} setDraft={setDraft} setText={setText} canEdit={canEdit} />}

          {!isException && section === "data" && (
            <>
              <Card title="SAVIO extension" description="Checks what is pasted, dropped, uploaded or sent on a page, on the PC itself. Only counts (“2 PAN numbers”) are recorded, never the text.">
                <ExtensionInstall form={form} setForm={setForm} canEdit={canEdit} />
              </Card>
              <Card title="When sensitive data is found"
                description={pilotUntil ? `Record only until ${pilotUntil.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" })}, the 14-day pilot.` : "What happens on the page."}>
                <div className="p-5 grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3" style={{ borderColor: "var(--border)" }}>
                  {MODES.map((m) => {
                    const locked = !!pilotUntil && m.value !== "log";
                    const on = form.guard_mode === m.value;
                    return (
                      <button key={m.value} type="button" disabled={!canEdit || locked}
                        onClick={() => setForm({ ...form, guard_mode: m.value })}
                        className="text-left rounded-lg p-3 disabled:cursor-not-allowed"
                        style={{ border: `1px solid ${on ? "var(--accent)" : "var(--border)"}`,
                                 background: on ? tint("var(--accent)", 8) : "var(--bg)", opacity: locked ? 0.5 : 1 }}>
                        <div className="text-sm font-medium" style={{ color: on ? "var(--accent)" : "var(--text-primary)" }}>{m.label}</div>
                        <div className="text-xs mt-1" style={muted}>{m.help}</div>
                      </button>
                    );
                  })}
                </div>
              </Card>
              <Card title="What is checked">
                <Setting title="Sites to check" help="One per line, e.g. chatgpt.com. Empty means every site." wide>
                  <Lines value={draft.text.watched} onChange={(v) => setText("watched", v)} disabled={!canEdit} />
                </Setting>
                <Setting title="Restricted keywords" help="One per line, e.g. a project code name. Matched as whole words." wide>
                  <Lines value={draft.text.keywords} onChange={(v) => setText("keywords", v)} disabled={!canEdit} />
                </Setting>
                <Setting title="Count but never act on" help="Still recorded, never warned about or stopped." wide>
                  <div className="flex flex-wrap gap-2">
                    {(Object.entries(FINDING_KINDS) as [FindingKind, string][]).map(([kind, label]) => {
                      const on = form.guard_ignore_kinds.includes(kind);
                      return (
                        <button key={kind} type="button" disabled={!canEdit}
                          onClick={() => setForm({ ...form, guard_ignore_kinds: on
                            ? form.guard_ignore_kinds.filter((x) => x !== kind) : [...form.guard_ignore_kinds, kind] })}
                          className="px-3 py-1 rounded-full text-xs font-medium"
                          style={on ? { background: tint("var(--accent)"), color: "var(--accent)", border: "1px solid var(--accent)" }
                                    : { ...field }}>
                          {label}
                        </button>
                      );
                    })}
                  </div>
                </Setting>
                <Setting title="Read the text inside PDFs"
                  help="Uploaded PDFs, and PDFs in the weekly check, are read on the PC like Word and Excel files. Off: an uploaded PDF counts as “could not check”.">
                  <Toggle label="Read PDFs" checked={form.guard_read_pdfs} disabled={!canEdit}
                    onChange={(v) => setForm({ ...form, guard_read_pdfs: v })} />
                </Setting>
                <Setting title="Find where sensitive files are kept"
                  help="Weekly, on each PC: the text, Word and Excel files in Desktop, Documents, Downloads and OneDrive. You see which folders hold Aadhaar, PAN, card or bank numbers and how many, never file names or contents.">
                  <Toggle label="Find sensitive files" checked={form.discovery_enabled} disabled={!canEdit}
                    onChange={(v) => setForm({ ...form, discovery_enabled: v })} />
                </Setting>
              </Card>
            </>
          )}

          {!isException && section === "accounts" && <Accounts draft={draft} setForm={setForm} setText={setText} canEdit={canEdit} />}

          {!isException && section === "usb" && (
            <Card title="USB drives and phones" description="Uses Windows' own settings. A change reaches each PC within the hour; drives already plugged in are reconnected then.">
              <Setting title="Access" help={USB_MODES.find((m) => m.value === form.usb_mode)?.help} wide>
                <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-2">
                  {USB_MODES.map((m) => {
                    const on = form.usb_mode === m.value;
                    return (
                      <button key={m.value} type="button" disabled={!canEdit} onClick={() => setForm({ ...form, usb_mode: m.value })}
                        className="text-left rounded-lg px-3 py-2 text-sm"
                        style={{ border: `1px solid ${on ? "var(--accent)" : "var(--border)"}`, background: on ? tint("var(--accent)", 8) : "var(--bg)",
                                 color: on ? "var(--accent)" : "var(--text-primary)", fontWeight: on ? 600 : 400 }}>
                        {m.label}
                      </button>
                    );
                  })}
                </div>
              </Setting>
              {form.usb_mode === "company_drives" && (
                <Setting title="Company drives" help="Only these drives work on PCs with this policy." wide>
                  <CompanyDrives form={form} setForm={setForm} canEdit={canEdit} />
                </Setting>
              )}
              <Setting title="Record what is copied onto USB drives"
                help="Each copy is checked on the PC once it finishes. You see what kind of data went onto a drive and who was signed in, never the files' names or contents. It does not stop the copy: the access setting does that.">
                <Toggle label="Record USB copies" checked={form.usb_observe} disabled={!canEdit}
                  onChange={(v) => setForm({ ...form, usb_observe: v })} />
              </Setting>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}

/** Who a named policy is for: teams (from Groups & Teams) and single people. */
function Assignment({ draft, setDraft, canEdit }: { draft: Draft; setDraft: (d: Draft) => void; canEdit: boolean }) {
  const { data: teams } = useQuery({ queryKey: ["user-teams"], queryFn: listUserTeams });
  const { data: users } = useQuery({ queryKey: ["all-users"], queryFn: listAllUsers });
  const byId = new Map((users ?? []).map((u) => [u.id, u]));
  const toggleTeam = (id: string) => setDraft({ ...draft, team_ids: draft.team_ids.includes(id)
    ? draft.team_ids.filter((x) => x !== id) : [...draft.team_ids, id] });
  return (
    <Card title="Assignment"
      description="Who this policy is for. A PC gets the policy of the person it is assigned to in Assets, so when someone is given another PC, their policy follows them there within the hour.">
      <Setting title="Policy name" help="Shown in the policy list and on each PC.">
        <input disabled={!canEdit} value={draft.name} maxLength={120} placeholder="e.g. Finance team"
          onChange={(e) => setDraft({ ...draft, name: e.target.value })}
          className="w-full sm:w-72 px-3 py-2 rounded-lg text-sm outline-none" style={field} />
      </Setting>
      <Setting title="Priority" help="When a person is covered by more than one policy, the lowest number wins. The default policy always comes last.">
        <input type="number" min={1} max={1000} disabled={!canEdit} value={draft.priority}
          onChange={(e) => setDraft({ ...draft, priority: Math.min(1000, Math.max(1, Number(e.target.value) || 1)) })}
          className="w-24 px-3 py-2 rounded-lg text-sm outline-none" style={field} />
      </Setting>
      <Setting title="Teams" help="Everyone in these teams. Teams are made under Groups & Teams." wide>
        {teams && !teams.length && <p className="text-xs" style={muted}>No teams yet. Create them under Groups &amp; Teams.</p>}
        <div className="flex flex-wrap gap-2">
          {(teams ?? []).map((t) => {
            const on = draft.team_ids.includes(t.id);
            return (
              <button key={t.id} type="button" disabled={!canEdit} onClick={() => toggleTeam(t.id)}
                className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm"
                style={on ? { background: tint("var(--accent)"), color: "var(--accent)", border: "1px solid var(--accent)", fontWeight: 600 }
                          : { ...field }}>
                {t.colour && <span className="h-2 w-2 rounded-full" style={{ background: t.colour }} />}
                {t.name}<span className="text-xs" style={muted}>{t.member_count}</span>
              </button>
            );
          })}
        </div>
      </Setting>
      <Setting title="People" help="Single users, on top of the teams above." wide>
        <div className="flex flex-wrap gap-2">
          {draft.user_ids.map((id) => (
            <Chip key={id} tone="accent" onRemove={canEdit ? () => setDraft({ ...draft, user_ids: draft.user_ids.filter((x) => x !== id) }) : undefined}>
              {byId.get(id)?.full_name ?? "Removed user"}
            </Chip>
          ))}
          {!draft.user_ids.length && <span className="text-xs" style={muted}>Nobody added one by one.</span>}
        </div>
        {canEdit && (
          <div className="sm:w-80">
            <SearchableSelect value="" placeholder="Add a person…" searchPlaceholder="Name or email"
              onChange={(id) => id && !draft.user_ids.includes(id) && setDraft({ ...draft, user_ids: [...draft.user_ids, id] })}
              options={(users ?? []).filter((u) => !draft.user_ids.includes(u.id))
                .map((u) => ({ value: u.id, label: u.full_name, sublabel: u.email, keywords: u.email }))} />
          </div>
        )}
      </Setting>
    </Card>
  );
}

function Sites({ draft, setDraft, setText, canEdit }: {
  draft: Draft; setDraft: (d: Draft) => void; setText: (k: TextKey, v: string) => void; canEdit: boolean;
}) {
  const { data: categories } = useQuery({ queryKey: ["site-categories"], queryFn: getSiteCategories, staleTime: Infinity });
  const form = draft.form;
  return (
    <>
      <Card title="Blocked and allowed sites">
        <Setting title="Blocked sites" help="One per line, e.g. wetransfer.com. Covers subdomains." wide>
          <Lines value={draft.text.blocked} onChange={(v) => setText("blocked", v)} disabled={!canEdit} rows={5} />
        </Setting>
        <Setting title="Always allowed" help="Exceptions to the blocked sites and categories, e.g. linkedin.com for a sales team." wide>
          <Lines value={draft.text.allowed} onChange={(v) => setText("allowed", v)} disabled={!canEdit} />
        </Setting>
        <Setting title="Google sign-in only for" help="Your Google Workspace domains, e.g. acme.in. Personal Gmail is then refused." wide>
          <Lines value={draft.text.google} onChange={(v) => setText("google", v)} disabled={!canEdit} rows={2} />
        </Setting>
      </Card>
      {categories && (
        <Card title="Site categories"
          description="Whole kinds of site, as a firewall's categories. Allowed wins over any block, including the blocked sites above.">
          <CategoryGrid categories={categories} canEdit={canEdit} neutral="No rule"
            allowed={form.allowed_categories ?? []} blocked={form.blocked_categories}
            onChange={(allowed, blocked) => setDraft({ ...draft, form: { ...form, allowed_categories: allowed, blocked_categories: blocked } })} />
          <p className="px-5 pb-4 text-xs" style={muted}>
            Adult sites and malware or spam are not listed: there are millions and they change daily, so blocking them needs
            filtering DNS rather than a list.
          </p>
        </Card>
      )}
    </>
  );
}

function Accounts({ draft, setForm, setText, canEdit }: {
  draft: Draft; setForm: (f: BrowserPolicy) => void; setText: (k: TextKey, v: string) => void; canEdit: boolean;
}) {
  const form = draft.form;
  const one = (k: "microsoft_tenant_id" | "microsoft_policy_id" | "slack_requester_id", title: string, help: string) => (
    <Setting title={title} help={help}>
      <input disabled={!canEdit} value={form[k] ?? ""} onChange={(e) => setForm({ ...form, [k]: e.target.value.trim() || null })}
        className="w-full sm:w-80 px-3 py-2 rounded-lg text-sm outline-none font-mono" style={field} />
    </Setting>
  );
  return (
    <>
      <Card title="Company accounts only"
        description="People can sign in to these services only with your organization's own accounts. Each service enforces it itself, on plans that support it; the SAVIO extension sends it your IDs (Microsoft 365 on the PC excepted). Leave a service empty to leave it alone.">
        <Setting title="Microsoft 365 on the PC too"
          help="Outlook, Teams, Word and the other Office apps, and Edge, through Windows' own tenant restrictions with the two IDs below; no extension needed. A wrong ID stops Office signing in, so try it on one team first.">
          <Toggle label="Microsoft 365 on the PC" checked={form.microsoft_on_windows} disabled={!canEdit}
            onChange={(v) => setForm({ ...form, microsoft_on_windows: v })} />
        </Setting>
        {one("microsoft_tenant_id", "Microsoft 365: tenant ID", "Entra → External Identities → Cross-tenant access settings → Default settings → Tenant restrictions.")}
        {one("microsoft_policy_id", "Microsoft 365: tenant restrictions policy ID", "The Policy ID on that same page.")}
        {one("slack_requester_id", "Slack: your workspace or org ID", "Like T0123ABCD or E0123ABCD, from Slack support.")}
        <Setting title="Slack: allowed workspace and org IDs" help="One per line, your own included." wide>
          <Lines value={draft.text.slack} onChange={(v) => setText("slack", v)} disabled={!canEdit} rows={2} />
        </Setting>
        <Setting title="Claude: allowed organization IDs" help="One per line, from Claude's admin settings." wide>
          <Lines value={draft.text.claude} onChange={(v) => setText("claude", v)} disabled={!canEdit} rows={2} />
        </Setting>
        <Setting title="ChatGPT: allowed workspace IDs" help="One per line, from the ChatGPT Enterprise admin settings." wide>
          <Lines value={draft.text.chatgpt} onChange={(v) => setText("chatgpt", v)} disabled={!canEdit} rows={2} />
        </Setting>
      </Card>
      <Card title="Other extensions allowed"
        description="With any service above set, private windows and guest mode are off and every other browser extension is blocked (another extension could undo these rules), except the ones listed here.">
        <Setting title="Extension IDs" help="One per line. Chrome and Edge IDs are 32 letters, from the extension's store page; Firefox IDs look like name@example.com." wide>
          <Lines value={draft.text.extensions} onChange={(v) => setText("extensions", v)} disabled={!canEdit} rows={3} />
        </Setting>
      </Card>
    </>
  );
}

/** Until the store listing: the extension loaded unpacked by IT, with the policy naming its fixed ID. */
function ExtensionInstall({ form, setForm, canEdit }: {
  form: BrowserPolicy; setForm: (f: BrowserPolicy) => void; canEdit: boolean;
}) {
  const [err, setErr] = useState<string | null>(null);
  const byHand = form.extension_install === "manual" && !!(form.chrome_extension_id || form.edge_extension_id);
  const turn = (on: boolean) => setForm(on
    ? { ...form, extension_install: "manual", chrome_extension_id: SAVIO_EXTENSION_ID, edge_extension_id: SAVIO_EXTENSION_ID,
        extension_developer_mode_off: false }
    : { ...form, extension_install: "store", chrome_extension_id: null, edge_extension_id: null });
  return (
    <>
      <Setting title="Use the extension in Chrome and Edge, installed by hand for now"
        help="Until it is listed in the Chrome and Edge stores. Extension developer mode stays allowed, because loading it needs it. Not Firefox yet: it only accepts the extension from Mozilla's store.">
        <Toggle label="Use the SAVIO extension" checked={byHand} disabled={!canEdit} onChange={turn} />
      </Setting>
      {byHand && (
        <div className="px-5 py-4 space-y-3 text-xs" style={{ borderColor: "var(--border)", color: "var(--text-primary)" }}>
          <div className="flex flex-wrap items-center gap-3">
            <button type="button" className="px-3 py-1.5 rounded-lg text-sm font-medium" style={button.primary}
              onClick={() => { setErr(null); downloadExtension().catch((e) => setErr(apiErrorMessage(e, "Could not download it."))); }}>
              Download the extension (zip)
            </button>
            <span style={muted}>Extension ID <span className="font-mono">{SAVIO_EXTENSION_ID}</span></span>
          </div>
          {err && <p style={{ color: "var(--health-bad)" }}>{err}</p>}
          <ol className="list-decimal pl-5 space-y-1">
            <li>Save the policy first, so the PC has it (within the hour).</li>
            <li>On the PC, unzip it to a folder that stays, e.g. <span className="font-mono">C:\SAVIO\savio-guard</span>. The browser
              loads it from there every time: deleting the folder removes the extension.</li>
            <li>Open <span className="font-mono">chrome://extensions</span> in Chrome or <span className="font-mono">edge://extensions</span> in Edge.</li>
            <li>Turn on <b>Developer mode</b>, click <b>Load unpacked</b> and pick the <span className="font-mono">savio-guard</span> folder.</li>
            <li>Check that its ID is the one above. Do this in each browser, and for each person who signs in to that PC.</li>
          </ol>
          <p style={muted}>A copy installed by hand can be removed by the person using the PC; one installed from the store, later, cannot.</p>
        </div>
      )}
    </>
  );
}

/** C3b: the approved company drives, and the drives seen on the org's PCs to approve from. */
function CompanyDrives({ form, setForm, canEdit }: {
  form: BrowserPolicy; setForm: (f: BrowserPolicy) => void; canEdit: boolean;
}) {
  const { data: seen } = useQuery({ queryKey: ["drives-seen"], queryFn: getDrivesSeen, enabled: canEdit, retry: false });
  const [names, setNames] = useState<Record<string, string>>({});
  const approved = new Set(form.usb_approved_drives.map((d) => d.id.toUpperCase()));
  const pending = (seen ?? []).filter((d) => !approved.has(d.id.toUpperCase()));
  return (
    <div className="space-y-3 text-sm" style={{ color: "var(--text-primary)" }}>
      <div className="rounded-lg divide-y" style={{ border: "1px solid var(--border)" }}>
        {!form.usb_approved_drives.length && (
          <p className="px-3 py-2 text-xs" style={{ color: "var(--health-warn)" }}>None approved yet: no USB drive will work on these PCs.</p>
        )}
        {form.usb_approved_drives.map((d) => (
          <div key={d.id} className="flex flex-wrap items-center gap-2 px-3 py-2 text-xs" style={{ borderColor: "var(--border)" }}>
            <span className="font-medium">{d.name}</span>
            <span className="font-mono truncate max-w-md" style={muted} title={d.id}>{d.id}</span>
            {canEdit && (
              <button type="button" className="ml-auto underline" style={muted}
                onClick={() => setForm({ ...form, usb_approved_drives: form.usb_approved_drives.filter((x) => x.id !== d.id) })}>
                remove
              </button>
            )}
          </div>
        ))}
      </div>
      {canEdit && (
        <div className="space-y-1">
          <div className="text-xs font-medium">Drives seen on your PCs</div>
          <p className="text-xs" style={muted}>Plug a new company drive into any PC with SAVIO; it shows up here within the hour.</p>
          {pending.map((d) => (
            <div key={d.id} className="flex flex-wrap items-center gap-2 text-xs py-1">
              <span>{d.name}</span>
              <span style={muted}>on {d.pcs.join(", ")}</span>
              {/* Windows made its ID up, so any drive of that model in that port would share it:
                  it cannot be approved on its own (review 3b L2). */}
              {!d.unique_serial ? <span style={{ color: "var(--health-warn)" }}>no serial number of its own, so it cannot be approved</span> : (
                <>
                  <input placeholder="Name, e.g. Accounts drive 1" maxLength={60} value={names[d.id] ?? ""}
                    onChange={(e) => setNames({ ...names, [d.id]: e.target.value })}
                    className="px-2 py-1 rounded text-xs outline-none" style={field} />
                  <button type="button" className="underline" style={{ color: "var(--accent)" }} disabled={!(names[d.id] ?? "").trim()}
                    onClick={() => setForm({ ...form, usb_approved_drives: [...form.usb_approved_drives,
                      { id: d.id, name: (names[d.id] ?? "").trim() }] })}>
                    Approve
                  </button>
                </>
              )}
            </div>
          ))}
          {seen && !pending.length && <p className="text-xs" style={muted}>No other drives seen.</p>}
          <p className="text-xs" style={muted}>Approving or removing takes effect when you save the policy.</p>
        </div>
      )}
    </div>
  );
}

/** Site categories, each allowed, blocked or left alone. */
function CategoryGrid({ categories, allowed, blocked, onChange, canEdit, neutral }: {
  categories: { key: string; label: string; hosts: string[] }[]; allowed: string[]; blocked: string[];
  onChange: (allowed: string[], blocked: string[]) => void; canEdit: boolean; neutral: string;
}) {
  const options = [{ value: "allow", label: "Allow", tone: "good" }, { value: "none", label: neutral },
                   { value: "block", label: "Block", tone: "bad" }] as const;
  return (
    <div className="p-5 grid grid-cols-1 md:grid-cols-2 gap-3" style={{ borderColor: "var(--border)" }}>
      {categories.map((c) => {
        const state = allowed.includes(c.key) ? "allow" : blocked.includes(c.key) ? "block" : "none";
        const tone = state === "allow" ? "var(--health-good)" : state === "block" ? "var(--health-bad)" : "var(--border)";
        return (
          <div key={c.key} className="rounded-lg p-3 space-y-2"
            style={{ border: `1px solid ${state === "none" ? "var(--border)" : tone}`, background: state === "none" ? "var(--bg)" : tint(tone, 6) }}>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>{c.label}</span>
              <Choice label={c.label} value={state} options={options} disabled={!canEdit}
                onChange={(v) => onChange(
                  [...allowed.filter((k) => k !== c.key), ...(v === "allow" ? [c.key] : [])],
                  [...blocked.filter((k) => k !== c.key), ...(v === "block" ? [c.key] : [])])} />
            </div>
            <div className="text-xs break-words" style={muted}>{c.hosts.join(", ")}</div>
          </div>
        );
      })}
    </div>
  );
}

const NO_CHANGE = "No change";

/** An exception's modules: each one left alone ("No change") unless set here. */
function ExceptionModules({ section, draft, setDraft, setText, canEdit, pilotUntil }: {
  section: Section; draft: Draft; setDraft: (d: Draft) => void; setText: (k: TextKey, v: string) => void;
  canEdit: boolean; pilotUntil: Date | null;
}) {
  const { data: categories } = useQuery({ queryKey: ["site-categories"], queryFn: getSiteCategories, staleTime: Infinity });
  const x = draft.exception;
  const set = (patch: Partial<ExceptionBody>) => setDraft({ ...draft, exception: { ...x, ...patch } });
  const tri = (v: boolean | null | undefined) => (v == null ? "leave" : v ? "on" : "off");
  const fromTri = (v: string) => (v === "leave" ? null : v === "on");
  const intro = "Only what you set here changes. Everything else stays as the person's full policy (or the default) has it.";

  if (section === "browser") {
    return (
      <Card title="Browser controls" description={intro}>
        {SWITCHES.filter((s) => s.key !== "extension_developer_mode_off").map((s) => {
          const key = s.key as "incognito_off" | "new_profiles_off" | "dev_tools_off" | "block_other_browsers";
          return (
            <Setting key={key} title={s.label} help={s.help}>
              <Choice label={s.label} value={tri(x[key])} disabled={!canEdit} onChange={(v) => set({ [key]: fromTri(v) })}
                options={[{ value: "leave", label: NO_CHANGE }, { value: "on", label: key === "block_other_browsers" ? "Close them" : "Block", tone: "bad" },
                          { value: "off", label: "Allow", tone: "good" }]} />
            </Setting>
          );
        })}
      </Card>
    );
  }
  if (section === "sites") {
    return (
      <>
        <Card title="Sites" description={`${intro} An allowed site wins over any block.`}>
          <Setting title="Also allow these sites" help="One per line, e.g. facebook.com. Allowed even where the full policy blocks them." wide>
            <Lines value={draft.text.xallow} onChange={(v) => setText("xallow", v)} disabled={!canEdit} rows={3} />
          </Setting>
          <Setting title="Also block these sites" help="One per line. Blocked even where the full policy allows them." wide>
            <Lines value={draft.text.xblock} onChange={(v) => setText("xblock", v)} disabled={!canEdit} rows={3} />
          </Setting>
          <Setting title="Google sign-in" help={draft.gmail === "company" ? "Only these Google Workspace domains, one per line, e.g. acme.in." : "Personal Gmail and other Google accounts."} wide>
            <Choice label="Google sign-in" value={draft.gmail} disabled={!canEdit} onChange={(v) => setDraft({ ...draft, gmail: v })}
              options={[{ value: "leave", label: NO_CHANGE }, { value: "personal", label: "Allow personal Gmail", tone: "good" },
                        { value: "company", label: "Company accounts only", tone: "bad" }]} />
            {draft.gmail === "company" && <Lines value={draft.text.xgoogle} onChange={(v) => setText("xgoogle", v)} disabled={!canEdit} rows={2} />}
          </Setting>
        </Card>
        {categories && (
          <Card title="Site categories" description="Allow or block whole kinds of site on top of the full policy.">
            <CategoryGrid categories={categories} canEdit={canEdit} neutral={NO_CHANGE}
              allowed={x.allow_categories ?? []} blocked={x.block_categories ?? []}
              onChange={(allow_categories, block_categories) => set({ allow_categories, block_categories })} />
          </Card>
        )}
      </>
    );
  }
  if (section === "data") {
    return (
      <Card title="When sensitive data is found" description={pilotUntil ? `${intro} Record only until the 14-day pilot ends.` : intro}>
        <div className="p-5 grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3" style={{ borderColor: "var(--border)" }}>
          {[{ value: null, label: NO_CHANGE, help: "As the full policy has it." }, ...MODES].map((m) => {
            const locked = !!pilotUntil && m.value !== null && m.value !== "log";
            const on = (x.guard_mode ?? null) === m.value;
            return (
              <button key={m.value ?? "leave"} type="button" disabled={!canEdit || locked} onClick={() => set({ guard_mode: m.value })}
                className="text-left rounded-lg p-3 disabled:cursor-not-allowed"
                style={{ border: `1px solid ${on ? "var(--accent)" : "var(--border)"}`, background: on ? tint("var(--accent)", 8) : "var(--bg)",
                         opacity: locked ? 0.5 : 1 }}>
                <div className="text-sm font-medium" style={{ color: on ? "var(--accent)" : "var(--text-primary)" }}>{m.label}</div>
                <div className="text-xs mt-1" style={muted}>{m.help}</div>
              </button>
            );
          })}
        </div>
      </Card>
    );
  }
  if (section === "usb") {
    return (
      <Card title="USB drives and phones" description={`${intro} Company drives are approved in a full policy.`}>
        <Setting title="Access" help={x.usb_mode ? USB_MODES.find((m) => m.value === x.usb_mode)?.help : "As the full policy has it."} wide>
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-2">
            {[{ value: null, label: NO_CHANGE }, ...USB_MODES.filter((m) => m.value !== "company_drives")].map((m) => {
              const on = (x.usb_mode ?? null) === m.value;
              return (
                <button key={m.value ?? "leave"} type="button" disabled={!canEdit} onClick={() => set({ usb_mode: m.value })}
                  className="text-left rounded-lg px-3 py-2 text-sm"
                  style={{ border: `1px solid ${on ? "var(--accent)" : "var(--border)"}`, background: on ? tint("var(--accent)", 8) : "var(--bg)",
                           color: on ? "var(--accent)" : "var(--text-primary)", fontWeight: on ? 600 : 400 }}>
                  {m.value === "off" ? "Allow (SAVIO sets nothing)" : m.label}
                </button>
              );
            })}
          </div>
        </Setting>
        <Setting title="Record what is copied onto USB drives" help="Counts of what kind of data went onto a drive, never file names or contents.">
          <Choice label="Record USB copies" value={tri(x.usb_observe)} disabled={!canEdit} onChange={(v) => set({ usb_observe: fromTri(v) })}
            options={[{ value: "leave", label: NO_CHANGE }, { value: "on", label: "Record" }, { value: "off", label: "Don't record" }]} />
        </Setting>
      </Card>
    );
  }
  return null;
}
