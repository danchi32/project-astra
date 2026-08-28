"use client";

import Link from "next/link";
import { useState } from "react";
import { Send, CheckCircle2, Loader2 } from "lucide-react";
import { site } from "@/lib/site";
import { useContent } from "@/lib/content";
import { getAttribution, trackEvent } from "@/lib/analytics";

type Status = "idle" | "submitting" | "success";

const inputCls =
  "w-full rounded-xl border border-token bg-app px-4 py-3 text-sm text-primary-token placeholder:text-muted-token focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/30";

export function ContactForm() {
  const { c, list } = useContent();
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({
    name: "",
    email: "",
    company: "",
    phone: "",
    interest: "ASTRA AI",
    message: "",
    website: "", // honeypot — must stay empty
  });

  function update<K extends keyof typeof form>(key: K, value: string) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  // Prefilled mailto used only when the server email isn't configured yet.
  function openMailto() {
    const subject = encodeURIComponent(
      `Inquiry: ${form.interest} — ${form.name}`,
    );
    const body = encodeURIComponent(
      `Name: ${form.name}\nEmail: ${form.email}\nCompany: ${form.company}\nPhone: ${form.phone}\nInterested in: ${form.interest}\n\n${form.message}`,
    );
    window.location.href = `mailto:${site.contact.sales}?subject=${subject}&body=${body}`;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setStatus("submitting");

    try {
      const res = await fetch("/contact.php", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...form, ...getAttribution() }),
      });
      const data = await res.json().catch(() => ({}));

      if (res.ok && data.ok) {
        // Email was sent to sales@ via the PHP handler.
        trackEvent("generate_lead", {
          lead_type: form.interest,
          form_name: "contact",
        });
        setStatus("success");
      } else if (res.status === 422) {
        // Validation error from the server.
        setStatus("idle");
        setError(data.error || "Please check your details and try again.");
      } else {
        // Handler not reachable (e.g. running locally) or a send error —
        // fall back to the visitor's mail client so the message isn't lost.
        setStatus("success");
        openMailto();
      }
    } catch {
      // Network error → fall back to mailto so the message isn't lost.
      setStatus("success");
      openMailto();
    }
  }

  if (status === "success") {
    return (
      <div className="flex flex-col items-center justify-center rounded-2xl border border-token bg-app p-10 text-center">
        <div className="grid h-14 w-14 place-items-center rounded-full bg-emerald-500/10 text-emerald-500">
          <CheckCircle2 className="h-7 w-7" />
        </div>
        <h3 className="mt-4 text-lg font-bold">
          {c("contact.form.successTitle", "Thank you!")}
        </h3>
        <p className="mt-2 max-w-sm text-sm text-secondary-token">
          {c(
            "contact.form.successText",
            "Your inquiry is on its way. Our team will get back to you shortly.",
          )}{" "}
          If your email client didn&apos;t open, reach us at{" "}
          <a
            href={`mailto:${site.contact.sales}`}
            className="font-medium text-brand-500"
          >
            {site.contact.sales}
          </a>
          .
        </p>
        <button
          onClick={() => setStatus("idle")}
          className="mt-5 text-sm font-medium text-brand-500 hover:underline"
        >
          {c("contact.form.another", "Send another message")}
        </button>
      </div>
    );
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="rounded-2xl border border-token bg-surface p-6 sm:p-8"
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label className="mb-1.5 block text-xs font-medium text-secondary-token">
            {c("contact.form.name", "Full name *")}
          </label>
          <input
            required
            value={form.name}
            onChange={(e) => update("name", e.target.value)}
            className={inputCls}
            placeholder="Jane Doe"
          />
        </div>
        <div>
          <label className="mb-1.5 block text-xs font-medium text-secondary-token">
            {c("contact.form.email", "Work email *")}
          </label>
          <input
            required
            type="email"
            value={form.email}
            onChange={(e) => update("email", e.target.value)}
            className={inputCls}
            placeholder="jane@company.com"
          />
        </div>
        <div>
          <label className="mb-1.5 block text-xs font-medium text-secondary-token">
            {c("contact.form.company", "Company")}
          </label>
          <input
            value={form.company}
            onChange={(e) => update("company", e.target.value)}
            className={inputCls}
            placeholder="Company Inc."
          />
        </div>
        <div>
          <label className="mb-1.5 block text-xs font-medium text-secondary-token">
            {c("contact.form.phone", "Phone")}
          </label>
          <input
            value={form.phone}
            onChange={(e) => update("phone", e.target.value)}
            className={inputCls}
            placeholder="+91 00000 00000"
          />
        </div>
      </div>

      <div className="mt-4">
        <label className="mb-1.5 block text-xs font-medium text-secondary-token">
          {c("contact.form.interestLabel", "I'm interested in")}
        </label>
        <select
          value={form.interest}
          onChange={(e) => update("interest", e.target.value)}
          className={inputCls}
        >
          {list<string>("contact.form.interests", [
            "ASTRA AI",
            "Managed IT Services",
            "Laptops & Hardware",
            "Partnership",
            "Something else",
          ]).map((opt) => (
            <option key={opt}>{opt}</option>
          ))}
        </select>
      </div>

      <div className="mt-4">
        <label className="mb-1.5 block text-xs font-medium text-secondary-token">
          {c("contact.form.message", "Message *")}
        </label>
        <textarea
          required
          rows={5}
          value={form.message}
          onChange={(e) => update("message", e.target.value)}
          className={inputCls}
          placeholder={c(
            "contact.form.messagePlaceholder",
            "Tell us about your requirements…",
          )}
        />
      </div>

      {/* Honeypot: hidden from users, catches bots. */}
      <div className="absolute left-[-9999px]" aria-hidden="true">
        <label>
          Leave this field empty
          <input
            tabIndex={-1}
            autoComplete="off"
            value={form.website}
            onChange={(e) => update("website", e.target.value)}
          />
        </label>
      </div>

      {error && (
        <p className="mt-4 rounded-lg bg-red-500/10 px-3 py-2 text-sm text-red-500">
          {error}
        </p>
      )}

      <button
        type="submit"
        disabled={status === "submitting"}
        className="mt-5 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-brand-600 px-5 py-3 text-sm font-semibold text-white shadow-lg shadow-brand-600/25 transition-all hover:bg-brand-500 disabled:opacity-60 sm:w-auto"
      >
        {status === "submitting" ? (
          <>
            <Loader2 className="h-4 w-4 animate-spin" />{" "}
            {c("contact.form.sending", "Sending…")}
          </>
        ) : (
          <>
            {c("contact.form.submit", "Send inquiry")}{" "}
            <Send className="h-4 w-4" />
          </>
        )}
      </button>

      {/* Transparency at the point of collection. The Privacy Policy explains what is
          done with an enquiry; a link here is what makes that notice meaningful. */}
      <p className="mt-3 text-xs leading-relaxed text-muted-token">
        By sending this enquiry you agree that {site.legal.displayName} may use your
        details to respond to you, as described in our{" "}
        <Link href="/privacy/" className="underline hover:text-brand-500">
          Privacy Policy
        </Link>
        .
      </p>
    </form>
  );
}
