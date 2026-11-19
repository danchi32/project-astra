"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Circle, ShieldAlert } from "lucide-react";
import { FINDING_KINDS, getDpdp, setPrivacyContact, type FindingKind } from "@/lib/api/guard";
import { isUpgradeRequired } from "@/components/upgrade-required";
import { apiErrorMessage } from "@/lib/utils";

// Phase 3b · I1 · AI Guard → DPDP readiness. What SAVIO's own records say about the org's
// safeguards for personal data: a score, what is left to do (each with its evidence and where to
// fix it), and where personal data is kept and goes. Never a legal claim. Admin only.

const WHERE: Record<string, string> = {
  file_sharing: "Personal file sharing", personal_email: "Personal e-mail", ai_chat: "AI chat", messaging: "Messaging",
  social_media: "Social media", paste_sites: "Paste sites", business: "Business tools", usb: "USB drives", other: "Other sites",
};

const status = (e: unknown) => (e as { response?: { status?: number } } | null)?.response?.status;

export default function DpdpPage() {
  const qc = useQueryClient();
  const { data, error, isLoading } = useQuery({ queryKey: ["dpdp"], queryFn: getDpdp, retry: false });
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  useEffect(() => { if (data) { setName(data.contact.name ?? ""); setEmail(data.contact.email ?? ""); } }, [data]);

  const muted = { color: "var(--text-secondary)" };
  const panel = { background: "var(--surface)", border: "1px solid var(--border)" };
  const input = { background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" };

  if (isUpgradeRequired(error) || status(error) === 403) {
    return (
      <div className="rounded-xl p-8 text-center max-w-lg mx-auto" style={panel}>
        <ShieldAlert size={22} className="mx-auto mb-3" style={{ color: "var(--accent)" }} />
        <h2 className="text-base font-semibold" style={{ color: "var(--text-primary)" }}>
          {isUpgradeRequired(error) ? "AI Guard is an add-on" : "Only an admin can see this"}
        </h2>
      </div>
    );
  }

  async function save() {
    setMsg(null);
    try {
      await setPrivacyContact(name.trim(), email.trim());
      setMsg({ ok: true, text: "Saved." });
      await qc.invalidateQueries({ queryKey: ["dpdp"] });
    } catch (e) { setMsg({ ok: false, text: apiErrorMessage(e, "Could not save.") }); }
  }

  const todo = data?.items.filter((i) => i.status === "todo") ?? [];
  const done = data?.items.filter((i) => i.status === "done") ?? [];
  const color = (data?.score ?? 0) >= 80 ? "#10b981" : (data?.score ?? 0) >= 50 ? "#f59e0b" : "#ef4444";

  return (
    <div className="space-y-4 max-w-5xl">
      <div className="flex items-start gap-3">
        <div className="p-2 rounded-lg" style={{ background: "rgba(37,99,235,0.12)", color: "var(--accent)" }}><ShieldAlert size={18} /></div>
        <div>
          <h1 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>DPDP readiness</h1>
          <p className="text-xs max-w-2xl" style={muted}>
            How ready your organisation is to look after personal data, from what SAVIO sees on your PCs: what is in place,
            what is left to do, and where personal data is kept and goes.
          </p>
        </div>
      </div>

      {isLoading && <p className="text-sm" style={muted}>Loading…</p>}
      {error && <p className="text-sm" style={{ color: "#ef4444" }}>{apiErrorMessage(error, "Could not load.")}</p>}

      {data && (
        <>
          <div className="rounded-xl p-5 flex flex-wrap items-center gap-6" style={panel}>
            <div className="text-4xl font-bold" style={{ color }}>{data.score}%</div>
            <div className="text-sm" style={{ color: "var(--text-primary)" }}>
              {data.done} of {data.total} in place.{" "}
              {todo.length ? `${todo.length} left to do, below.` : "Nothing left on this list."}
              <p className="text-xs mt-1 max-w-xl" style={muted}>{data.disclaimer}</p>
            </div>
          </div>

          {todo.length > 0 && (
            <div className="space-y-2">
              <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>To do</h2>
              {todo.map((i) => (
                <div key={i.key} className="rounded-xl p-4 flex items-start gap-3" style={panel}>
                  <Circle size={16} className="mt-0.5 shrink-0" style={{ color: "#f59e0b" }} />
                  <div className="text-sm flex-1" style={{ color: "var(--text-primary)" }}>
                    <div className="font-medium">{i.title}</div>
                    <div className="text-xs" style={muted}>{i.detail} {i.why}</div>
                  </div>
                  {i.key !== "contact" && <Link href={i.link} className="text-xs underline" style={{ color: "var(--accent)" }}>Fix this</Link>}
                </div>
              ))}
            </div>
          )}

          <div className="rounded-xl p-4 space-y-2" style={panel}>
            <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Privacy and breach contact</h2>
            <p className="text-xs" style={muted}>The person who answers privacy complaints and owns a data breach from the first hour.</p>
            <div className="flex flex-wrap gap-2 items-center">
              <input aria-label="Name" placeholder="Name" maxLength={120} value={name} onChange={(e) => setName(e.target.value)}
                className="px-3 py-2 rounded-lg text-sm outline-none" style={input} />
              <input aria-label="E-mail" placeholder="E-mail" type="email" maxLength={254} value={email}
                onChange={(e) => setEmail(e.target.value)} className="px-3 py-2 rounded-lg text-sm outline-none" style={input} />
              <button onClick={save} className="px-3 py-2 rounded-lg text-sm font-medium text-white" style={{ background: "var(--accent)" }}>Save</button>
              {msg && <span className="text-xs" style={{ color: msg.ok ? "#10b981" : "#ef4444" }}>{msg.text}</span>}
            </div>
          </div>

          {data.retention.length > 0 && (
            <div id="retention" className="rounded-xl p-4 space-y-2" style={panel}>
              <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Still needed? Old personal data to review</h2>
              <p className="text-xs" style={muted}>
                Files with personal data nobody has changed in over two years, by folder. Ask the owner whether each is still
                needed: delete what is not, and move what must be kept to a restricted archive.
              </p>
              <table className="w-full text-xs">
                <thead><tr>{["PC", "Folder", "Old files", "With personal data", "Contact lists"].map((h) => (
                  <th key={h} className="text-left py-1 pr-3 uppercase whitespace-nowrap" style={muted}>{h}</th>))}</tr></thead>
                <tbody>
                  {data.retention.map((r) => (
                    <tr key={`${r.hostname}${r.path}`} style={{ color: "var(--text-primary)" }}>
                      <td className="py-1 pr-3">{r.hostname}</td>
                      <td className="py-1 pr-3 font-mono break-all">{r.path}</td>
                      <td className="py-1 pr-3">{r.old.toLocaleString()}</td>
                      <td className="py-1 pr-3">{r.files_with_findings.toLocaleString()}</td>
                      <td className="py-1 pr-3">{r.contact_lists.toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div className="rounded-xl p-4 flex flex-wrap items-center gap-3 text-sm" style={{ ...panel, color: "var(--text-primary)" }}>
            <div className="flex-1">
              <h2 className="text-sm font-semibold">If personal data gets out</h2>
              <p className="text-xs" style={muted}>Write it down the moment it is found and work through the steps; the record prints as an incident report.</p>
            </div>
            <Link href="/guard/incidents" className="text-xs underline" style={{ color: "var(--accent)" }}>Breach records</Link>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="rounded-xl p-4 space-y-1 text-sm" style={{ ...panel, color: "var(--text-primary)" }}>
              <h2 className="text-sm font-semibold">Personal data kept on PCs</h2>
              <p className="text-xs" style={muted}>
                {data.map.on_pcs.files.toLocaleString()} files on {data.map.on_pcs.pcs} PCs
                {data.map.on_pcs.contact_lists ? `, ${data.map.on_pcs.contact_lists} of them contact lists` : ""}.
              </p>
              {Object.entries(data.map.on_pcs.kinds).map(([k, n]) => (
                <div key={k} className="flex justify-between text-xs"><span>{FINDING_KINDS[k as FindingKind] ?? k}</span><span>{n.toLocaleString()}</span></div>
              ))}
              <Link href="/guard/discovery" className="text-xs underline" style={{ color: "var(--accent)" }}>Where it is, by folder</Link>
            </div>
            <div className="rounded-xl p-4 space-y-1 text-sm" style={{ ...panel, color: "var(--text-primary)" }}>
              <h2 className="text-sm font-semibold">Where it went, last 30 days</h2>
              <p className="text-xs" style={muted}>{data.map.leaving.events.toLocaleString()} times personal data left a PC through the browser or onto USB.</p>
              {Object.entries(data.map.leaving.where).map(([k, n]) => (
                <div key={k} className="flex justify-between text-xs"><span>{WHERE[k] ?? k}</span><span>{n.toLocaleString()}</span></div>
              ))}
              <Link href="/guard/cases" className="text-xs underline" style={{ color: "var(--accent)" }}>Cases</Link>
            </div>
          </div>

          {done.length > 0 && (
            <div className="space-y-1">
              <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>In place</h2>
              {done.map((i) => (
                <div key={i.key} className="flex items-start gap-2 text-sm" style={{ color: "var(--text-primary)" }}>
                  <CheckCircle2 size={16} className="mt-0.5 shrink-0" style={{ color: "#10b981" }} />
                  <span>{i.title} <span className="text-xs" style={muted}>· {i.detail}</span></span>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
