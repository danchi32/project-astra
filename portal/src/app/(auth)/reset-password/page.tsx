"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { confirmPasswordReset } from "@/lib/api/auth";

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

  const inputStyle = { background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" } as const;
  const inputCls = "w-full px-3 py-2 rounded-lg text-sm outline-none focus:ring-2 focus:ring-brand-500";

  return (
    <div className="min-h-screen flex items-center justify-center" style={{ background: "var(--bg)" }}>
      <div className="w-full max-w-sm p-8 rounded-xl shadow-lg" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
        <div className="mb-6 text-center">
          <div className="inline-flex items-center gap-2 text-2xl font-bold" style={{ color: "var(--accent)" }}>
            <span className="text-3xl">⬡</span> ASTRA
          </div>
          <p className="mt-1 text-sm" style={{ color: "var(--text-secondary)" }}>Choose a new password</p>
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
              <label className="block text-sm font-medium mb-1" style={{ color: "var(--text-secondary)" }}>New password</label>
              <input type="password" required value={password} onChange={(e) => setPassword(e.target.value)}
                className={inputCls} style={inputStyle} placeholder="At least 8 characters" />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1" style={{ color: "var(--text-secondary)" }}>Confirm new password</label>
              <input type="password" required value={confirm} onChange={(e) => setConfirm(e.target.value)}
                className={inputCls} style={inputStyle} placeholder="Re-enter password" />
            </div>

            {error && <p className="text-sm text-red-500 text-center">{error}</p>}

            <button type="submit" disabled={loading}
              className="w-full py-2 rounded-lg text-sm font-semibold text-white transition-opacity disabled:opacity-50"
              style={{ background: "var(--accent)" }}>
              {loading ? "Resetting…" : "Reset password"}
            </button>
            <p className="text-center text-sm">
              <Link href="/login" className="font-medium" style={{ color: "var(--text-secondary)" }}>Back to sign in</Link>
            </p>
          </form>
        )}
      </div>
    </div>
  );
}
