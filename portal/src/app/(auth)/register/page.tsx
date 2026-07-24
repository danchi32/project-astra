"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { registerStart, registerVerify } from "@/lib/api/auth";

export default function RegisterPage() {
  const router = useRouter();
  const [form, setForm] = useState({
    organization_name: "",
    admin_name: "",
    admin_email: "",
    admin_password: "",
  });
  const [step, setStep] = useState<"details" | "code">("details");
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  function set(field: keyof typeof form) {
    return (e: React.ChangeEvent<HTMLInputElement>) => setForm({ ...form, [field]: e.target.value });
  }

  async function submitDetails(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (form.admin_password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    setLoading(true);
    try {
      const res = await registerStart(form);
      if (res.otp_required) {
        setStep("code");
      } else {
        router.push("/dashboard"); // email off — created immediately
      }
    } catch (err) {
      // Surface the backend's message (e.g. "Your organisation is already registered") so the
      // user sees the real reason, with a sensible fallback.
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(detail || "Couldn't start signup. That email may already be registered — try signing in instead.");
    } finally {
      setLoading(false);
    }
  }

  async function submitCode(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await registerVerify(form.admin_email, code.trim());
      router.push("/dashboard");
    } catch {
      setError("That code isn't right or has expired. Check your email, or go back and try again.");
    } finally {
      setLoading(false);
    }
  }

  const inputStyle = {
    background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)",
  } as const;
  const inputCls = "w-full px-3 py-2 rounded-lg text-sm outline-none focus:ring-2 focus:ring-brand-500";
  const labelCls = "block text-sm font-medium mb-1";

  return (
    <div className="min-h-screen flex items-center justify-center py-10" style={{ background: "var(--bg)" }}>
      <div className="w-full max-w-sm p-8 rounded-xl shadow-lg" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
        <div className="mb-6 text-center">
          <div className="inline-flex items-center gap-2 text-2xl font-bold" style={{ color: "var(--accent)" }}>
            <span className="text-3xl">⬡</span> ASTRA
          </div>
          <p className="mt-1 text-sm" style={{ color: "var(--text-secondary)" }}>
            {step === "details" ? "Create your organization" : "Confirm your email"}
          </p>
        </div>

        {step === "details" ? (
          <form onSubmit={submitDetails} className="space-y-4">
            <div>
              <label className={labelCls} style={{ color: "var(--text-secondary)" }}>Organization name</label>
              <input required value={form.organization_name} onChange={set("organization_name")}
                className={inputCls} style={inputStyle} placeholder="Acme Corp" />
            </div>
            <div>
              <label className={labelCls} style={{ color: "var(--text-secondary)" }}>Your name</label>
              <input required value={form.admin_name} onChange={set("admin_name")}
                className={inputCls} style={inputStyle} placeholder="Jane Admin" />
            </div>
            <div>
              <label className={labelCls} style={{ color: "var(--text-secondary)" }}>Email</label>
              <input type="email" required value={form.admin_email} onChange={set("admin_email")}
                className={inputCls} style={inputStyle} placeholder="admin@acme.com" />
            </div>
            <div>
              <label className={labelCls} style={{ color: "var(--text-secondary)" }}>Password</label>
              <input type="password" required value={form.admin_password} onChange={set("admin_password")}
                className={inputCls} style={inputStyle} placeholder="At least 8 characters" />
            </div>

            {error && <p className="text-sm text-red-500 text-center">{error}</p>}

            <button type="submit" disabled={loading}
              className="w-full py-2 rounded-lg text-sm font-semibold text-white transition-opacity disabled:opacity-50"
              style={{ background: "var(--accent)" }}>
              {loading ? "Please wait…" : "Continue"}
            </button>
          </form>
        ) : (
          <form onSubmit={submitCode} className="space-y-4">
            <p className="text-sm text-center" style={{ color: "var(--text-secondary)" }}>
              We emailed a 6-digit code to <strong style={{ color: "var(--text-primary)" }}>{form.admin_email}</strong>. Enter it to finish.
            </p>
            <input required value={code} onChange={(e) => setCode(e.target.value)}
              inputMode="numeric" autoFocus placeholder="123456"
              className="w-full px-3 py-2 rounded-lg text-center text-lg tracking-[0.4em] font-mono outline-none focus:ring-2 focus:ring-brand-500"
              style={inputStyle} />

            {error && <p className="text-sm text-red-500 text-center">{error}</p>}

            <button type="submit" disabled={loading}
              className="w-full py-2 rounded-lg text-sm font-semibold text-white transition-opacity disabled:opacity-50"
              style={{ background: "var(--accent)" }}>
              {loading ? "Verifying…" : "Create organization"}
            </button>
            <button type="button" onClick={() => { setStep("details"); setError(""); setCode(""); }}
              className="w-full text-sm" style={{ color: "var(--text-secondary)" }}>
              ← Back to edit details
            </button>
          </form>
        )}

        <p className="mt-5 text-center text-sm" style={{ color: "var(--text-secondary)" }}>
          Already have an account?{" "}
          <Link href="/login" className="font-medium" style={{ color: "var(--accent)" }}>Sign in</Link>
        </p>
      </div>
    </div>
  );
}
