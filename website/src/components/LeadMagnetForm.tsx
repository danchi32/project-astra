"use client";

import { useState } from "react";
import { Download, Loader2, CheckCircle2, ArrowRight } from "lucide-react";
import { bookDemo } from "@/lib/site";
import { getAttribution, trackEvent } from "@/lib/analytics";

type Status = "idle" | "submitting" | "done";

const inputCls =
  "w-full rounded-xl border border-token bg-app px-4 py-3 text-sm text-primary-token placeholder:text-muted-token focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/30";

/**
 * Email-gated lead magnet. On submit it notifies sales@ via the same PHP mailer
 * as the contact form (with attribution), fires a `generate_lead` event, then
 * reveals + auto-starts the download. Soft-gated: capture first, deliver second.
 */
export function LeadMagnetForm({
  assetUrl,
  assetName,
  leadLabel,
}: {
  assetUrl: string;
  assetName: string;
  leadLabel: string;
}) {
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({ name: "", email: "", company: "", website: "" });

  function update<K extends keyof typeof form>(key: K, value: string) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  function deliver() {
    trackEvent("generate_lead", { lead_type: "lead_magnet", form_name: leadLabel });
    setStatus("done");
    // Auto-start the download for a smooth hand-off.
    if (typeof window !== "undefined") window.open(assetUrl, "_blank", "noopener");
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setStatus("submitting");

    const payload = {
      name: form.name,
      email: form.email,
      company: form.company,
      phone: "",
      interest: `Lead magnet — ${assetName}`,
      message: `Requested the "${assetName}" download.`,
      website: form.website, // honeypot
      ...getAttribution(),
    };

    try {
      const res = await fetch("/contact.php", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json().catch(() => ({}));
      if (res.status === 422) {
        setStatus("idle");
        setError(data.error || "Please check your details and try again.");
        return;
      }
      // On success OR if the mailer isn't reachable, still deliver the asset —
      // we never block a lead from the resource they asked for.
      deliver();
    } catch {
      deliver();
    }
  }

  if (status === "done") {
    return (
      <div className="rounded-2xl border border-token bg-app p-8 text-center">
        <div className="mx-auto grid h-14 w-14 place-items-center rounded-full bg-emerald-500/10 text-emerald-500">
          <CheckCircle2 className="h-7 w-7" />
        </div>
        <h3 className="mt-4 text-lg font-bold">Your checklist is ready</h3>
        <p className="mx-auto mt-2 max-w-xs text-sm text-secondary-token">
          The download should have started. If not, grab it here:
        </p>
        <a
          href={assetUrl}
          target="_blank"
          rel="noopener"
          className="mt-5 inline-flex items-center justify-center gap-2 rounded-xl bg-brand-600 px-5 py-3 text-sm font-semibold text-white shadow-lg shadow-brand-600/25 transition-all hover:bg-brand-500"
        >
          <Download className="h-4 w-4" /> Download the PDF
        </a>
        <a
          href={bookDemo.href}
          {...(bookDemo.external ? { target: "_blank", rel: "noopener" } : {})}
          className="mt-3 block text-sm font-medium text-brand-500 hover:underline"
        >
          Want to automate this? Book a demo →
        </a>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="rounded-2xl border border-token bg-surface p-6 sm:p-7">
      <p className="text-sm font-semibold">Get the free PDF</p>
      <p className="mt-1 text-xs text-secondary-token">
        Enter your details and the checklist is yours — instantly.
      </p>
      <div className="mt-5 grid gap-3">
        <input
          required
          value={form.name}
          onChange={(e) => update("name", e.target.value)}
          className={inputCls}
          placeholder="Full name *"
          aria-label="Full name"
        />
        <input
          required
          type="email"
          value={form.email}
          onChange={(e) => update("email", e.target.value)}
          className={inputCls}
          placeholder="Work email *"
          aria-label="Work email"
        />
        <input
          value={form.company}
          onChange={(e) => update("company", e.target.value)}
          className={inputCls}
          placeholder="Company (optional)"
          aria-label="Company"
        />
      </div>

      {/* Honeypot */}
      <div className="absolute left-[-9999px]" aria-hidden="true">
        <label>
          Leave empty
          <input
            tabIndex={-1}
            autoComplete="off"
            value={form.website}
            onChange={(e) => update("website", e.target.value)}
          />
        </label>
      </div>

      {error && (
        <p className="mt-4 rounded-lg bg-red-500/10 px-3 py-2 text-sm text-red-500">{error}</p>
      )}

      <button
        type="submit"
        disabled={status === "submitting"}
        className="mt-5 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-brand-600 px-5 py-3 text-sm font-semibold text-white shadow-lg shadow-brand-600/25 transition-all hover:bg-brand-500 disabled:opacity-60"
      >
        {status === "submitting" ? (
          <>
            <Loader2 className="h-4 w-4 animate-spin" /> Sending…
          </>
        ) : (
          <>
            Send me the checklist <ArrowRight className="h-4 w-4" />
          </>
        )}
      </button>
      <p className="mt-3 text-center text-[11px] text-muted-token">
        No spam. We&apos;ll email you the checklist and the occasional IT-automation tip. Unsubscribe anytime.
      </p>
    </form>
  );
}
