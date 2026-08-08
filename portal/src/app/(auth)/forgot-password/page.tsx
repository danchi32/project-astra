"use client";
import { useState } from "react";
import Link from "next/link";
import { requestPasswordReset } from "@/lib/api/auth";
import {
  AuthShell,
  authButtonCls,
  authInputCls,
  authInputStyle,
} from "@/components/auth-shell";

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
    <AuthShell subtitle="Reset your password">
      <div className="hidden lg:block mb-8">
        <h2 className="text-2xl font-semibold tracking-tight" style={{ color: "var(--text-primary)" }}>
          Reset your password
        </h2>
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
            className={authInputCls} style={authInputStyle} placeholder="admin@company.com" />
          <button type="submit" disabled={loading} className={authButtonCls}
            style={{ background: "var(--accent)" }}>
            {loading ? "Sending…" : "Send reset link"}
          </button>
          <p className="text-center text-sm">
            <Link href="/login" className="font-medium" style={{ color: "var(--text-secondary)" }}>Back to sign in</Link>
          </p>
        </form>
      )}
    </AuthShell>
  );
}
