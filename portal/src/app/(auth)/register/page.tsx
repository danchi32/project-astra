"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { register } from "@/lib/api/auth";

export default function RegisterPage() {
  const router = useRouter();
  const [form, setForm] = useState({
    invite_code: "",
    organization_name: "",
    admin_name: "",
    admin_email: "",
    admin_password: "",
  });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  function set(field: keyof typeof form) {
    return (e: React.ChangeEvent<HTMLInputElement>) => setForm({ ...form, [field]: e.target.value });
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (form.admin_password.length < 12) {
      setError("Password must be at least 12 characters.");
      return;
    }
    setLoading(true);
    try {
      await register(form);
      router.push("/dashboard");
    } catch {
      setError("Couldn't create the organization. Check your invite code (it may be invalid, expired, or used) and that the email isn't already registered.");
    } finally {
      setLoading(false);
    }
  }

  const inputStyle = {
    background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)",
  } as const;
  const inputCls = "w-full px-3 py-2 rounded-lg text-sm outline-none focus:ring-2 focus:ring-blue-500";
  const labelCls = "block text-sm font-medium mb-1";

  return (
    <div className="min-h-screen flex items-center justify-center py-10" style={{ background: "var(--bg)" }}>
      <div className="w-full max-w-sm p-8 rounded-xl shadow-lg" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
        <div className="mb-6 text-center">
          <div className="inline-flex items-center gap-2 text-2xl font-bold" style={{ color: "var(--accent)" }}>
            <span className="text-3xl">⬡</span> ASTRA
          </div>
          <p className="mt-1 text-sm" style={{ color: "var(--text-secondary)" }}>
            Create your organization
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className={labelCls} style={{ color: "var(--text-secondary)" }}>Invite code</label>
            <input required value={form.invite_code} onChange={set("invite_code")}
              className={inputCls} style={inputStyle} placeholder="Provided by ASTRA" />
          </div>
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
              className={inputCls} style={inputStyle} placeholder="At least 12 characters" />
          </div>

          {error && <p className="text-sm text-red-500 text-center">{error}</p>}

          <button type="submit" disabled={loading}
            className="w-full py-2 rounded-lg text-sm font-semibold text-white transition-opacity disabled:opacity-50"
            style={{ background: "var(--accent)" }}>
            {loading ? "Creating…" : "Create organization"}
          </button>
        </form>

        <p className="mt-5 text-center text-sm" style={{ color: "var(--text-secondary)" }}>
          Already have an account?{" "}
          <Link href="/login" className="font-medium" style={{ color: "var(--accent)" }}>Sign in</Link>
        </p>
      </div>
    </div>
  );
}
