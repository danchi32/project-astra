"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { login } from "@/lib/api/auth";
import {
  AuthShell,
  authButtonCls,
  authInputCls,
  authInputStyle,
  authLabelCls,
} from "@/components/auth-shell";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(email, password);
      router.push("/dashboard");
    } catch {
      setError("Invalid email or password.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthShell subtitle="AI Operations Platform">
      <div className="hidden lg:block mb-8">
        <h2 className="text-2xl font-semibold tracking-tight" style={{ color: "var(--text-primary)" }}>
          Sign in
        </h2>
        <p className="mt-1 text-sm" style={{ color: "var(--text-secondary)" }}>
          Welcome back — pick up where your fleet left off.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className={authLabelCls} style={{ color: "var(--text-secondary)" }}>Email</label>
          <input
            type="email"
            required
            autoComplete="username"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className={authInputCls}
            style={authInputStyle}
            placeholder="admin@company.com"
          />
        </div>
        <div>
          <label className={authLabelCls} style={{ color: "var(--text-secondary)" }}>Password</label>
          <input
            type="password"
            required
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className={authInputCls}
            style={authInputStyle}
            placeholder="••••••••••••"
          />
        </div>

        {error && <p className="text-sm text-red-500 text-center">{error}</p>}

        <button type="submit" disabled={loading} className={authButtonCls}
          style={{ background: "var(--accent)" }}>
          {loading ? "Signing in…" : "Sign in"}
        </button>
      </form>

      <p className="mt-4 text-center text-sm">
        <Link href="/forgot-password" className="font-medium" style={{ color: "var(--accent)" }}>Forgot password?</Link>
      </p>

      <p className="mt-3 text-center text-sm" style={{ color: "var(--text-secondary)" }}>
        Don&apos;t have an account?{" "}
        <Link href="/register" className="font-medium" style={{ color: "var(--accent)" }}>Sign up</Link>
        {" "}— free for 14 days, no card needed.
      </p>
    </AuthShell>
  );
}
