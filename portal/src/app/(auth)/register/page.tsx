"use client";
import { useState } from "react";
import { ChevronDown, Eye, EyeOff } from "lucide-react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { registerStart, registerVerify } from "@/lib/api/auth";
import { apiErrorMessage } from "@/lib/utils";
import { phoneWithCountry } from "@/lib/phone";
import { COUNTRIES } from "@/lib/countries";

// Policies live on the marketing site, which is where they are published and versioned.
const TERMS_URL = "https://technomateai.com/terms/";
const PRIVACY_URL = "https://technomateai.com/privacy/";
import {
  AuthShell,
  SIGNUP_STEPS,
  TRIAL_POINTS,
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
    phone: "",
    admin_password: "",
  });
  // The phone's country, by ISO code (dial codes are shared: +1 is US and Canada). India by
  // default, the market SAVIO sells in first.
  const [country, setCountry] = useState("IN");
  // Unticked by default. A pre-ticked box is not acceptance of anything.
  const [termsAccepted, setTermsAccepted] = useState(false);
  const [step, setStep] = useState<"details" | "code">("details");
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  function set(field: keyof typeof form) {
    return (e: React.ChangeEvent<HTMLInputElement>) => setForm({ ...form, [field]: e.target.value });
  }

  async function submitDetails(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    const dial = COUNTRIES.find((c) => c.iso === country)?.dial ?? "91";
    const phone = phoneWithCountry(dial, form.phone);
    if (!phone) {
      setError("Enter a valid phone number for the selected country.");
      return;
    }
    if (form.admin_password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    // The server refuses this too. Checking here as well turns a 400 into an
    // explanation the person can act on without a round trip.
    if (!termsAccepted) {
      setError("Please accept the Terms of Service and Privacy Policy to continue.");
      return;
    }
    setLoading(true);
    try {
      const res = await registerStart({ ...form, phone, terms_accepted: termsAccepted });
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
    <AuthShell
      subtitle={step === "details" ? "Start your 14-day free trial" : "Confirm your email"}
      eyebrow="14-day free trial"
      headline="Start free. No credit card."
      blurb="Create your organization, install the agent on one device, and SAVIO starts reporting on it. Nothing to pay until you decide it's worth it."
      points={TRIAL_POINTS}
      footer={SIGNUP_STEPS}
    >
      <div className="hidden lg:block mb-8">
        <h2 className="text-2xl font-semibold tracking-tight" style={{ color: "var(--text-primary)" }}>
          {step === "details" ? "Sign up" : "Confirm your email"}
        </h2>
        <p className="mt-1 text-sm" style={{ color: "var(--text-secondary)" }}>
          {step === "details"
            ? "Takes a minute. No credit card needed."
            : "One more step and your organization is ready."}
        </p>
      </div>

      {step === "details" ? (
        <form onSubmit={submitDetails} className="space-y-4">
          <div>
            <label className={authLabelCls} style={{ color: "var(--text-secondary)" }}>Organization name</label>
            <input required autoComplete="organization" value={form.organization_name} onChange={set("organization_name")}
              className={authInputCls} style={authInputStyle} placeholder="Acme Corp" />
          </div>
          <div>
            <label className={authLabelCls} style={{ color: "var(--text-secondary)" }}>Your name</label>
            <input required autoComplete="name" value={form.admin_name} onChange={set("admin_name")}
              className={authInputCls} style={authInputStyle} placeholder="Jane Admin" />
          </div>
          <div>
            <label className={authLabelCls} style={{ color: "var(--text-secondary)" }}>Work email</label>
            <input type="email" required autoComplete="email" value={form.admin_email} onChange={set("admin_email")}
              className={authInputCls} style={authInputStyle} placeholder="admin@yourcompany.com" />
            {/* Say it up front — the backend rejects personal providers, and finding that
                out only after submitting (and after the OTP email) is a poor first run. */}
            <p className="text-xs mt-1.5" style={{ color: "var(--text-secondary)" }}>
              Use your company email — personal addresses (Gmail, Outlook, Yahoo…) aren&apos;t accepted.
            </p>
          </div>
          <div>
            <label className={authLabelCls} style={{ color: "var(--text-secondary)" }}>Phone number</label>
            <div className="flex gap-2">
              {/* A native select, invisible, over a compact "IN +91" label: closed, a full
                  country name doesn't fit beside the number; open, the names are what
                  people scan and type-search by. */}
              <div className={`${authInputCls} relative flex items-center justify-between gap-1 focus-within:ring-2`}
                style={{ ...authInputStyle, width: "6.5rem", flexShrink: 0 }}>
                <span>{country} +{COUNTRIES.find((c) => c.iso === country)?.dial}</span>
                <ChevronDown size={14} style={{ color: "var(--text-secondary)" }} />
                <select aria-label="Country code" value={country}
                  onChange={(e) => setCountry(e.target.value)}
                  className="absolute inset-0 w-full cursor-pointer opacity-0">
                  {COUNTRIES.map((c) => (
                    <option key={c.iso} value={c.iso}>{`${c.name} (+${c.dial})`}</option>
                  ))}
                </select>
              </div>
              <input type="tel" required autoComplete="tel-national" value={form.phone} onChange={set("phone")}
                className={`${authInputCls} min-w-0`} style={authInputStyle} placeholder="85954 92500" />
            </div>
          </div>
          <div>
            <label className={authLabelCls} style={{ color: "var(--text-secondary)" }}>Password</label>
            <div className="relative">
              <input type={showPassword ? "text" : "password"} required autoComplete="new-password"
                minLength={8} value={form.admin_password} onChange={set("admin_password")}
                className={`${authInputCls} pr-11`} style={authInputStyle} placeholder="At least 8 characters" />
              <button type="button" onClick={() => setShowPassword((shown) => !shown)}
                aria-label={showPassword ? "Hide password" : "Show password"}
                className="absolute inset-y-0 right-0 grid w-11 place-items-center"
                style={{ color: "var(--text-secondary)" }}>
                {showPassword ? <EyeOff size={17} /> : <Eye size={17} />}
              </button>
            </div>
          </div>

          {/* Clickwrap. The acceptance, its version and the source address are recorded
              against the organisation — see backend migration 0054. */}
          <label className="flex items-start gap-2.5 text-xs leading-relaxed cursor-pointer"
            style={{ color: "var(--text-secondary)" }}>
            <input
              type="checkbox"
              checked={termsAccepted}
              onChange={(e) => setTermsAccepted(e.target.checked)}
              className="mt-0.5 h-4 w-4 shrink-0 rounded accent-brand-600"
            />
            <span>
              I agree to the{" "}
              <a href={TERMS_URL} target="_blank" rel="noopener noreferrer"
                className="underline hover:text-brand-500">Terms of Service</a>{" "}
              and{" "}
              <a href={PRIVACY_URL} target="_blank" rel="noopener noreferrer"
                className="underline hover:text-brand-500">Privacy Policy</a>{" "}
              of Technomate IT-Solution Private Limited, and confirm I am authorised to
              accept them for my organization.
            </span>
          </label>

          {error && <p className="text-sm text-red-500 text-center">{error}</p>}

          <button type="submit" disabled={loading || !termsAccepted} className={authButtonCls}
            style={{ background: "var(--accent)" }}>
            {loading ? "Creating your trial…" : "Start my 14-day trial"}
          </button>
        </form>
      ) : (
        <form onSubmit={submitCode} className="space-y-4">
          <p className="text-sm text-center" style={{ color: "var(--text-secondary)" }}>
            We emailed a 6-digit code to <strong style={{ color: "var(--text-primary)" }}>{form.admin_email}</strong>. Enter it to finish.
          </p>
          <input required value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
            maxLength={6} autoComplete="one-time-code"
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
