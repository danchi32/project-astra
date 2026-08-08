"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { confirmPasswordReset } from "@/lib/api/auth";
import {
  AuthShell,
  authButtonCls,
  authInputCls,
  authInputStyle,
  authLabelCls,
} from "@/components/auth-shell";

export default function ResetPasswordPage() {
  const router = useRouter();
  const [token, setToken] = useState<string | null>(null);
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);
  const [loading, setLoading] = useState(false);

  // Read the token from the URL client-side (avoids the useSearchParams Suspense rule).
  useEffect(() => {
    setToken(new URLSearchParams(window.location.search).get("token"));
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (password.length < 8) { setError("Password must be at least 8 characters."); return; }
    if (password !== confirm) { setError("Passwords don't match."); return; }
    if (!token) { setError("This reset link is missing its token. Request a new one."); return; }
    setLoading(true);
    try {
      await confirmPasswordReset(token, password);
      setDone(true);
      setTimeout(() => router.push("/login"), 2000);
    } catch {
      setError("This reset link is invalid or has expired. Request a new one.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthShell subtitle="Choose a new password">
      <div className="hidden lg:block mb-8">
        <h2 className="text-2xl font-semibold tracking-tight" style={{ color: "var(--text-primary)" }}>
          Choose a new password
        </h2>
      </div>

      {done ? (
        <div className="text-center space-y-4">
          <p className="text-sm" style={{ color: "var(--text-primary)" }}>
            Your password has been reset. Redirecting you to sign in…
          </p>
          <Link href="/login" className="inline-block text-sm font-medium" style={{ color: "var(--accent)" }}>Sign in now</Link>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className={authLabelCls} style={{ color: "var(--text-secondary)" }}>New password</label>
            <input type="password" required value={password} onChange={(e) => setPassword(e.target.value)}
              className={authInputCls} style={authInputStyle} placeholder="At least 8 characters" />
          </div>
          <div>
            <label className={authLabelCls} style={{ color: "var(--text-secondary)" }}>Confirm new password</label>
            <input type="password" required value={confirm} onChange={(e) => setConfirm(e.target.value)}
              className={authInputCls} style={authInputStyle} placeholder="Re-enter password" />
          </div>

          {error && <p className="text-sm text-red-500 text-center">{error}</p>}

          <button type="submit" disabled={loading} className={authButtonCls}
            style={{ background: "var(--accent)" }}>
            {loading ? "Resetting…" : "Reset password"}
          </button>
          <p className="text-center text-sm">
            <Link href="/login" className="font-medium" style={{ color: "var(--text-secondary)" }}>Back to sign in</Link>
          </p>
        </form>
      )}
    </AuthShell>
  );
}
