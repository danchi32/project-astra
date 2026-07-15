"use client";
import { useState } from "react";
import Link from "next/link";
import { requestPasswordReset } from "@/lib/api/auth";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      await requestPasswordReset(email.trim());
    } finally {
      setLoading(false);
      setSent(true); // always show the same confirmation (no account enumeration)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center" style={{ background: "var(--bg)" }}>
      <div className="w-full max-w-sm p-8 rounded-xl shadow-lg" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
        <div className="mb-6 text-center">
          <div className="inline-flex items-center gap-2 text-2xl font-bold" style={{ color: "var(--accent)" }}>
            <span className="text-3xl">⬡</span> ASTRA
          </div>
          <p className="mt-1 text-sm" style={{ color: "var(--text-secondary)" }}>Reset your password</p>
        </div>

        {sent ? (
          <div className="text-center space-y-4">
            <p className="text-sm" style={{ color: "var(--text-primary)" }}>
              If <strong>{email}</strong> has an account, we&apos;ve emailed a link to reset your password.
              Check your inbox (and spam).
            </p>
            <Link href="/login" className="inline-block text-sm font-medium" style={{ color: "var(--accent)" }}>← Back to sign in</Link>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
              Enter your email and we&apos;ll send you a link to set a new password.
            </p>
            <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)}
              className="w-full px-3 py-2 rounded-lg text-sm outline-none focus:ring-2 focus:ring-blue-500"
              style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
              placeholder="admin@company.com" />
            <button type="submit" disabled={loading}
              className="w-full py-2 rounded-lg text-sm font-semibold text-white transition-opacity disabled:opacity-50"
              style={{ background: "var(--accent)" }}>
              {loading ? "Sending…" : "Send reset link"}
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
