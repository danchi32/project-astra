"use client";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { UserRound } from "lucide-react";
import { getMe } from "@/lib/api/auth";
import { listAllUsers } from "@/lib/api/users";
import { getAccounts, assignAccount } from "@/lib/api/tracker";

function formatDay(day: string | null): string {
  if (!day) return "—";
  const [y, m, d] = day.split("-").map(Number);
  if (!y || !m || !d) return day;
  return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString(undefined, {
    day: "numeric", month: "short", year: "numeric", timeZone: "UTC",
  });
}

/** Configuration > People: map each tracked Windows account (ACME\\rahul) to a directory user,
 *  so attendance and productivity can roll up by person and team. Admin assigns; others read. */
export function AccountConfig() {
  const qc = useQueryClient();
  const { data: me } = useQuery({ queryKey: ["me"], queryFn: getMe });
  const isAdmin = me?.role === "admin";

  const { data: accounts } = useQuery({ queryKey: ["tracker-accounts"], queryFn: getAccounts });
  const { data: users } = useQuery({ queryKey: ["users-all"], queryFn: listAllUsers });

  const assign = useMutation({
    mutationFn: ({ username, userId }: { username: string; userId: string | null }) =>
      assignAccount(username, userId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tracker-accounts"] });
      // Attendance rows now carry the person, so refresh those views too.
      qc.invalidateQueries({ queryKey: ["tracker-attendance"] });
    },
  });

  const rows = accounts ?? [];
  const userList = users ?? [];

  return (
    <section className="space-y-4">
      <div>
        <h2 className="text-base font-semibold" style={{ color: "var(--text-primary)" }}>
          People
        </h2>
        <p className="text-sm mt-0.5" style={{ color: "var(--text-secondary)" }}>
          Map each tracked Windows account to a person, so attendance and productivity roll up by
          user and team. {!isAdmin && "Only an admin can change these."}
        </p>
      </div>

      <div className="rounded-2xl overflow-hidden" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr style={{ borderBottom: "1px solid var(--border)" }}>
                {["Account", "Last seen", "Devices", "Mapped to"].map((h) => (
                  <th key={h} className="px-5 py-3 text-left text-xs font-medium uppercase tracking-wide"
                    style={{ color: "var(--text-secondary)" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((a) => (
                <tr key={a.username} style={{ borderBottom: "1px solid var(--border)" }}>
                  <td className="px-5 py-3 font-medium" style={{ color: "var(--text-primary)" }}>{a.username}</td>
                  <td className="px-5 py-3" style={{ color: "var(--text-secondary)" }}>{formatDay(a.last_seen)}</td>
                  <td className="px-5 py-3 tabular-nums" style={{ color: "var(--text-secondary)" }}>{a.device_count}</td>
                  <td className="px-5 py-3">
                    <select
                      value={a.user_id ?? ""}
                      disabled={!isAdmin || assign.isPending}
                      onChange={(e) => assign.mutate({ username: a.username, userId: e.target.value || null })}
                      className="px-2 py-1.5 rounded-lg text-sm outline-none disabled:opacity-60 max-w-[240px]"
                      style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
                    >
                      <option value="">Unmapped</option>
                      {userList.map((u) => (
                        <option key={u.id} value={u.id}>{u.full_name} ({u.email})</option>
                      ))}
                    </select>
                  </td>
                </tr>
              ))}
              {rows.length === 0 && (
                <tr>
                  <td colSpan={4} className="px-5 py-8 text-center" style={{ color: "var(--text-secondary)" }}>
                    <UserRound size={18} className="inline mb-1 opacity-60" />
                    <div>No tracked accounts yet — they appear once agents report activity.</div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}
