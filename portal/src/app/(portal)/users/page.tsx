"use client";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Users as UsersIcon, Plus, Trash2, Upload } from "lucide-react";
import { listUsers, createUser, updateUser, deleteUser } from "@/lib/api/users";
import { getMe } from "@/lib/api/auth";
import type { UserRole } from "@/lib/api/types";

const ROLES: UserRole[] = ["admin", "technician", "user"];

type ImportRow = { email: string; full_name: string; role: UserRole; password: string };

// Parse a simple CSV: columns email, full_name, role, password (one user per line).
function parseCsvUsers(text: string): ImportRow[] {
  const rows: ImportRow[] = [];
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim();
    if (!line) continue;
    const cols = line.split(",").map((c) => c.trim());
    const email = (cols[0] ?? "").toLowerCase();
    if (!email || email === "email") continue; // skip blanks and a header row
    const roleRaw = (cols[2] ?? "user").toLowerCase();
    const role = (ROLES.includes(roleRaw as UserRole) ? roleRaw : "user") as UserRole;
    rows.push({ email, full_name: cols[1] ?? "", role, password: cols[3] ?? "" });
  }
  return rows;
}

const ROLE_STYLE: Record<UserRole, { color: string; bg: string }> = {
  admin: { color: "#ef4444", bg: "rgba(239,68,68,0.1)" },
  technician: { color: "#b246d4", bg: "rgba(59,130,246,0.1)" },
  user: { color: "#64748b", bg: "rgba(100,116,139,0.1)" },
};

export default function UsersPage() {
  const queryClient = useQueryClient();
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState({ email: "", full_name: "", password: "", role: "user" as UserRole });
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [importing, setImporting] = useState(false);
  const [importText, setImportText] = useState("email,full_name,role,password\n");
  const [importBusy, setImportBusy] = useState(false);
  const [importResult, setImportResult] = useState<{ created: number; errors: string[] } | null>(null);

  const { data: me } = useQuery({ queryKey: ["me"], queryFn: getMe });
  const { data: users, isLoading } = useQuery({ queryKey: ["users"], queryFn: listUsers });
  const isAdmin = me?.role === "admin";

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setSaving(true);
    try {
      await createUser(form);
      setForm({ email: "", full_name: "", password: "", role: "user" });
      setAdding(false);
      await queryClient.invalidateQueries({ queryKey: ["users"] });
    } catch {
      setError("Couldn't create the user (email may already exist, or the password is under 8 characters).");
    } finally {
      setSaving(false);
    }
  }

  async function changeRole(id: string, role: UserRole) {
    await updateUser(id, { role });
    await queryClient.invalidateQueries({ queryKey: ["users"] });
  }

  async function toggleActive(id: string, is_active: boolean) {
    await updateUser(id, { is_active });
    await queryClient.invalidateQueries({ queryKey: ["users"] });
  }

  async function remove(id: string) {
    await deleteUser(id);
    await queryClient.invalidateQueries({ queryKey: ["users"] });
  }

  function onCsvFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => setImportText(String(reader.result ?? ""));
    reader.readAsText(file);
  }

  async function runImport() {
    setImportBusy(true);
    setImportResult(null);
    const rows = parseCsvUsers(importText);
    let created = 0;
    const errors: string[] = [];
    for (const row of rows) {
      if (!row.email || !row.full_name || !row.password) {
        errors.push(`${row.email || "(no email)"}: needs email, full name, and password`);
        continue;
      }
      try {
        await createUser(row);
        created++;
      } catch {
        errors.push(`${row.email}: failed (email already exists, or password under 8 chars)`);
      }
    }
    setImportResult({ created, errors });
    await queryClient.invalidateQueries({ queryKey: ["users"] });
    setImportBusy(false);
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="p-2 rounded-lg" style={{ background: "rgba(154,47,187,0.1)", color: "var(--accent)" }}>
            <UsersIcon size={18} />
          </div>
          <div>
            <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>Users</h1>
            <p className="text-sm mt-0.5" style={{ color: "var(--text-secondary)" }}>
              People in your organization and their roles
            </p>
          </div>
        </div>
        {isAdmin && (
          <div className="flex gap-2">
            <button onClick={() => { setImporting((v) => !v); setImportResult(null); }}
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium"
              style={{ background: "var(--surface)", border: "1px solid var(--border)", color: "var(--text-primary)" }}>
              <Upload size={16} /> Bulk import
            </button>
            <button onClick={() => setAdding((a) => !a)}
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium text-white"
              style={{ background: "var(--accent)" }}>
              <Plus size={16} /> Add user
            </button>
          </div>
        )}
      </div>

      {importing && isAdmin && (
        <div className="rounded-xl p-4 space-y-3" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
            Paste rows or upload a CSV with columns{" "}
            <span className="font-mono" style={{ color: "var(--text-primary)" }}>email, full_name, role, password</span>{" "}
            — one user per line. Role is <span className="font-mono">admin</span>/<span className="font-mono">technician</span>/<span className="font-mono">user</span> (defaults to user); password must be at least 8 characters.
          </p>
          <input type="file" accept=".csv,text/csv" onChange={onCsvFile}
            className="block text-sm" style={{ color: "var(--text-secondary)" }} />
          <textarea value={importText} onChange={(e) => setImportText(e.target.value)} rows={6}
            className="w-full px-3 py-2 rounded-lg text-xs font-mono outline-none focus:ring-2 focus:ring-brand-500"
            style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }} />
          <div className="flex gap-2">
            <button onClick={runImport} disabled={importBusy}
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50"
              style={{ background: "var(--accent)" }}>
              <Upload size={15} /> {importBusy ? "Importing…" : "Import users"}
            </button>
            <button onClick={() => { setImporting(false); setImportResult(null); }}
              className="px-3 py-2 rounded-lg text-sm font-medium"
              style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-secondary)" }}>Close</button>
          </div>
          {importResult && (
            <div className="text-sm space-y-1">
              <p style={{ color: "#10b981" }}>{importResult.created} user(s) created.</p>
              {importResult.errors.length > 0 && (
                <>
                  <p className="text-red-500">{importResult.errors.length} row(s) failed:</p>
                  <ul className="text-xs list-disc pl-5" style={{ color: "var(--text-secondary)" }}>
                    {importResult.errors.map((er, i) => <li key={i}>{er}</li>)}
                  </ul>
                </>
              )}
            </div>
          )}
        </div>
      )}

      {adding && isAdmin && (
        <form onSubmit={save} className="rounded-xl p-4 grid grid-cols-1 md:grid-cols-4 gap-3"
          style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
          <input required type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })}
            placeholder="Email" className="px-3 py-2 rounded-lg text-sm outline-none focus:ring-2 focus:ring-brand-500"
            style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }} />
          <input required value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })}
            placeholder="Full name" className="px-3 py-2 rounded-lg text-sm outline-none focus:ring-2 focus:ring-brand-500"
            style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }} />
          <input required type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })}
            placeholder="Password (min 8 chars)" className="px-3 py-2 rounded-lg text-sm outline-none focus:ring-2 focus:ring-brand-500"
            style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }} />
          <div className="flex gap-2">
            <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value as UserRole })}
              className="flex-1 px-3 py-2 rounded-lg text-sm outline-none capitalize"
              style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }}>
              {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
            </select>
            <button type="submit" disabled={saving} className="px-3 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50"
              style={{ background: "var(--accent)" }}>{saving ? "…" : "Save"}</button>
          </div>
          {error && <p className="text-sm text-red-500 md:col-span-4">{error}</p>}
        </form>
      )}

      <div className="rounded-xl overflow-hidden" style={{ border: "1px solid var(--border)" }}>
        <div className="overflow-x-auto" style={{ background: "var(--surface)" }}>
          <table className="w-full text-sm whitespace-nowrap">
            <thead>
              <tr style={{ borderBottom: "1px solid var(--border)" }}>
                {["Name", "Email", "Role", "Status", "Joined", ""].map((h) => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide"
                    style={{ color: "var(--text-secondary)" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {isLoading && <tr><td colSpan={6} className="px-4 py-8 text-center" style={{ color: "var(--text-secondary)" }}>Loading…</td></tr>}
              {users?.map((u) => (
                <tr key={u.id} style={{ borderBottom: "1px solid var(--border)" }}>
                  <td className="px-4 py-3 font-medium" style={{ color: "var(--text-primary)" }}>{u.full_name}</td>
                  <td className="px-4 py-3" style={{ color: "var(--text-secondary)" }}>{u.email}</td>
                  <td className="px-4 py-3">
                    {isAdmin && u.id !== me?.id ? (
                      <select value={u.role} onChange={(e) => changeRole(u.id, e.target.value as UserRole)}
                        className="px-2 py-1 rounded-lg text-xs capitalize outline-none"
                        style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }}>
                        {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
                      </select>
                    ) : (
                      <span className="text-xs font-medium px-2 py-0.5 rounded-full capitalize"
                        style={{ color: ROLE_STYLE[u.role].color, background: ROLE_STYLE[u.role].bg }}>{u.role}</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <span className="text-xs font-medium" style={{ color: u.is_active ? "#10b981" : "#64748b" }}>
                      {u.is_active ? "Active" : "Disabled"}
                    </span>
                  </td>
                  <td className="px-4 py-3" style={{ color: "var(--text-secondary)" }}>{new Date(u.created_at).toLocaleDateString()}</td>
                  <td className="px-4 py-3 text-right">
                    {isAdmin && u.id !== me?.id && (
                      <div className="flex gap-2 justify-end">
                        <button onClick={() => toggleActive(u.id, !u.is_active)}
                          className="text-xs px-2 py-1 rounded-lg"
                          style={{ background: "var(--bg)", color: "var(--text-secondary)", border: "1px solid var(--border)" }}>
                          {u.is_active ? "Disable" : "Enable"}
                        </button>
                        <button onClick={() => remove(u.id)} title="Delete"
                          className="p-1 rounded-lg hover:bg-red-500/10 hover:text-red-500" style={{ color: "var(--text-secondary)" }}>
                          <Trash2 size={14} />
                        </button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
