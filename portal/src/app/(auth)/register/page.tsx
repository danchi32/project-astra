"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { registerStart, registerVerify } from "@/lib/api/auth";
import { apiErrorMessage } from "@/lib/utils";
import {
  AuthShell,
  authButtonCls,
  authInputCls,
  authInputStyle,
  authLabelCls,
} from "@/components/auth-shell";

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
      // user sees the real reason, with a sensible fallback. apiErrorMessage coerces a
      // validation-error array to a string so it can never crash the render.
      setError(apiErrorMessage(err, "Couldn't start signup. That email may already be registered — try signing in instead."));
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

  return (
    <AuthShell subtitle={step === "details" ? "Create your organization" : "Confirm your email"}>
      <div className="hidden lg:block mb-8">
        <h2 className="text-2xl font-semibold tracking-tight" style={{ color: "var(--text-primary)" }}>
          {step === "details" ? "Create your organization" : "Confirm your email"}
        </h2>
        <p className="mt-1 text-sm" style={{ color: "var(--text-secondary)" }}>
          {step === "details"
            ? "Takes a minute. Install the agent on one device and ASTRA starts reporting on it."
            : "One more step and your organization is ready."}
        </p>
      </div>

      {step === "details" ? (
        <form onSubmit={submitDetails} className="space-y-4">
          <div>
            <label className={authLabelCls} style={{ color: "var(--text-secondary)" }}>Organization name</label>
            <input required value={form.organization_name} onChange={set("organization_name")}
              className={authInputCls} style={authInputStyle} placeholder="Acme Corp" />
          </div>
          <div>
            <label className={authLabelCls} style={{ color: "var(--text-secondary)" }}>Your name</label>
            <input required value={form.admin_name} onChange={set("admin_name")}
              className={authInputCls} style={authInputStyle} placeholder="Jane Admin" />
          </div>
          <div>
            <label className={authLabelCls} style={{ color: "var(--text-secondary)" }}>Work email</label>
            <input type="email" required value={form.admin_email} onChange={set("admin_email")}
              className={authInputCls} style={authInputStyle} placeholder="admin@yourcompany.com" />
            {/* Say it up front — the backend rejects personal providers, and finding that
                out only after submitting (and after the OTP email) is a poor first run. */}
            <p className="text-xs mt-1.5" style={{ color: "var(--text-secondary)" }}>
              Use your company email — personal addresses (Gmail, Outlook, Yahoo…) aren&apos;t accepted.
            </p>
          </div>
          <div>
            <label className={authLabelCls} style={{ color: "var(--text-secondary)" }}>Password</label>
            <input type="password" required value={form.admin_password} onChange={set("admin_password")}
              className={authInputCls} style={authInputStyle} placeholder="At least 8 characters" />
          </div>

          {error && <p className="text-sm text-red-500 text-center">{error}</p>}

          <button type="submit" disabled={loading} className={authButtonCls}
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
            className="w-full px-3 py-2.5 rounded-lg text-center text-lg tracking-[0.4em] font-mono outline-none focus:ring-2 focus:ring-brand-500"
            style={authInputStyle} />

          {error && <p className="text-sm text-red-500 text-center">{error}</p>}

          <button type="submit" disabled={loading} className={authButtonCls}
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
    </AuthShell>
  );
}
