"use client";
import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Building2, Check, AlertTriangle } from "lucide-react";
import { getBillingProfile, updateBillingProfile } from "@/lib/api/billing-profile";
import { apiErrorMessage } from "@/lib/utils";
import type { BillingProfile } from "@/lib/api/types";

/** Label + value rather than a field per tax regime, matching the backend. An Indian
 *  customer picks GSTIN, an EU one VAT — the invoice prints whichever they chose. */
const TAX_LABELS = ["GSTIN", "VAT", "ABN", "TRN", "EIN", "Tax ID"];

type FieldKey = keyof Omit<BillingProfile, "complete">;

const FIELDS: { key: FieldKey; label: string; placeholder?: string; span?: boolean }[] = [
  { key: "legal_name", label: "Company legal name", placeholder: "Acme Technologies Pvt Ltd", span: true },
  { key: "billing_contact_name", label: "Billing contact" },
  { key: "billing_email", label: "Billing email", placeholder: "accounts@acme.com" },
  { key: "address_line1", label: "Address", span: true },
  { key: "address_line2", label: "Address line 2", span: true },
  { key: "city", label: "City" },
  { key: "state", label: "State / region" },
  { key: "postal_code", label: "ZIP / postcode" },
  { key: "country_code", label: "Country (2-letter code)", placeholder: "IN" },
  { key: "registration_number", label: "Registration number (optional)" },
];

/** What an invoice cannot be raised without. Mirrors the backend's own list — shown so a
 *  half-filled profile says which field is still missing rather than just failing later. */
const REQUIRED: FieldKey[] = ["legal_name", "billing_email", "address_line1", "city", "country_code"];

export function BillingDetailsForm({ canEdit }: { canEdit: boolean }) {
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ["billing-profile"], queryFn: getBillingProfile });

  const [form, setForm] = useState<Partial<BillingProfile>>({});
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  // Seed once the profile arrives. Not on every render, or typing would be overwritten by
  // the last fetch while someone is mid-edit.
  useEffect(() => {
    if (data) setForm(data);
  }, [data]);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true); setMsg(null);
    try {
      // Only what changed. The API treats an omitted field as "leave it", which is what
      // makes filling this in over several sittings work.
      const changed: Record<string, unknown> = {};
      for (const { key } of FIELDS) if (form[key] !== data?.[key]) changed[key] = form[key] || null;
      if (form.tax_id_label !== data?.tax_id_label) changed.tax_id_label = form.tax_id_label || null;
      if (form.tax_id !== data?.tax_id) changed.tax_id = form.tax_id || null;

      const next = await updateBillingProfile(changed);
      qc.setQueryData(["billing-profile"], next);
      setMsg({ ok: true, text: "Billing details saved." });
    } catch (e2) {
      setMsg({ ok: false, text: apiErrorMessage(e2, "Couldn't save the billing details.") });
    } finally {
      setSaving(false);
    }
  }

  const missing = REQUIRED.filter((k) => !form[k]);

  return (
    <form onSubmit={save} className="rounded-xl p-5"
      style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
      <div className="flex items-start gap-3">
        <div className="p-2 rounded-lg shrink-0" style={{ background: "rgba(154,47,187,0.1)", color: "var(--accent)" }}>
          <Building2 size={18} />
        </div>
        <div className="flex-1 min-w-0">
          <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Billing &amp; tax details</h2>
          <p className="text-xs mt-0.5" style={{ color: "var(--text-secondary)" }}>
            The legal entity and tax number printed on your invoices.
          </p>
        </div>
        {data?.complete && (
          <span className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-full shrink-0"
            style={{ color: "#10b981", background: "rgba(16,185,129,0.10)" }}>
            <Check size={12} /> Complete
          </span>
        )}
      </div>

      {/* Says WHICH fields are missing. "Incomplete" on its own sends someone hunting. */}
      {!data?.complete && missing.length > 0 && (
        <p className="mt-3 text-xs flex items-start gap-1.5" style={{ color: "#f59e0b" }}>
          <AlertTriangle size={13} className="shrink-0 mt-0.5" />
          <span>
            Still needed for an invoice:{" "}
            {missing.map((k) => FIELDS.find((f) => f.key === k)?.label).join(", ")}.
          </span>
        </p>
      )}

      <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-3">
        {FIELDS.map(({ key, label, placeholder, span }) => (
          <div key={key} className={span ? "sm:col-span-2" : ""}>
            <label className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>{label}</label>
            <input
              value={(form[key] as string) ?? ""}
              onChange={(e) => setForm({ ...form, [key]: e.target.value })}
              placeholder={placeholder}
              disabled={!canEdit}
              maxLength={key === "country_code" ? 2 : undefined}
              className="w-full mt-1 px-3 py-2 rounded-lg text-sm outline-none focus:ring-2 focus:ring-brand-500 disabled:opacity-60"
              style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
            />
          </div>
        ))}

        <div className="sm:col-span-2 grid grid-cols-3 gap-3">
          <div>
            <label className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>Tax number type</label>
            <select
              value={form.tax_id_label ?? ""}
              onChange={(e) => setForm({ ...form, tax_id_label: e.target.value })}
              disabled={!canEdit}
              className="w-full mt-1 px-3 py-2 rounded-lg text-sm outline-none disabled:opacity-60"
              style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
            >
              <option value="">—</option>
              {TAX_LABELS.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
          <div className="col-span-2">
            <label className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>
              {form.tax_id_label || "Tax"} number
            </label>
            <input
              value={form.tax_id ?? ""}
              onChange={(e) => setForm({ ...form, tax_id: e.target.value })}
              placeholder="29ABCDE1234F1Z5"
              disabled={!canEdit}
              className="w-full mt-1 px-3 py-2 rounded-lg text-sm outline-none focus:ring-2 focus:ring-brand-500 disabled:opacity-60"
              style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
            />
          </div>
        </div>
      </div>

      {msg && (
        <p className="mt-3 text-sm" style={{ color: msg.ok ? "#10b981" : "#ef4444" }}>{msg.text}</p>
      )}

      {canEdit ? (
        <button type="submit" disabled={saving}
          className="mt-4 px-4 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50"
          style={{ background: "var(--accent)" }}>
          {saving ? "Saving…" : "Save billing details"}
        </button>
      ) : (
        // Readable by anyone in the org — they may need the billing contact — but only an
        // admin changes the legal identity invoices are raised against.
        <p className="mt-4 text-xs" style={{ color: "var(--text-secondary)" }}>
          Only an organization admin can change these.
        </p>
      )}
    </form>
  );
}
