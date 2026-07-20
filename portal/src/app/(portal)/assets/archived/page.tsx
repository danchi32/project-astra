"use client";
import { useState } from "react";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Archive, ArrowLeft, History, RotateCcw, Trash2 } from "lucide-react";
import { listAssets, restoreAsset, deleteAsset } from "@/lib/api/assets";
import { getMe } from "@/lib/api/auth";
import { AssetPassportDrawer } from "@/components/asset-passport-drawer";
import type { Asset, AssetStatus } from "@/lib/api/types";

const STATUS_STYLE: Record<AssetStatus, { label: string; color: string }> = {
  in_use: { label: "In use", color: "#10b981" },
  in_storage: { label: "Idle", color: "#3b82f6" },
  in_repair: { label: "In repair", color: "#f59e0b" },
  retired: { label: "Retired", color: "#64748b" },
  lost: { label: "Lost", color: "#ef4444" },
};

export default function ArchivedAssetsPage() {
  const queryClient = useQueryClient();
  const { data: me } = useQuery({ queryKey: ["me"], queryFn: getMe });
  const { data: assets, isLoading } = useQuery({
    queryKey: ["assets", "archived"],
    queryFn: () => listAssets(true),
  });
  const [passportFor, setPassportFor] = useState<Asset | null>(null);
  const isStaff = me?.role === "admin" || me?.role === "technician";
  const isAdmin = me?.role === "admin";

  async function refresh() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["assets"] }),
      queryClient.invalidateQueries({ queryKey: ["asset-summary"] }),
    ]);
  }
  async function restore(id: string) {
    await restoreAsset(id);
    await refresh();
  }
  async function removeForever(id: string, name: string) {
    if (!confirm(`Permanently delete "${name}"?\n\nThis ERASES the asset and its entire passport history and cannot be undone.`)) return;
    await deleteAsset(id);
    await refresh();
  }

  return (
    <div className="space-y-6">
      <Link href="/assets" className="inline-flex items-center gap-1.5 text-sm" style={{ color: "var(--text-secondary)" }}>
        <ArrowLeft size={15} /> Back to assets
      </Link>

      <div className="flex items-center gap-2">
        <div className="p-2 rounded-lg" style={{ background: "rgba(37,99,235,0.1)", color: "var(--accent)" }}>
          <Archive size={18} />
        </div>
        <div>
          <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>Archived assets</h1>
          <p className="text-sm mt-0.5" style={{ color: "var(--text-secondary)" }}>
            Retired from the active register — their full history is preserved and they can be restored
          </p>
        </div>
      </div>

      <div className="rounded-xl overflow-hidden" style={{ border: "1px solid var(--border)" }}>
        <div className="overflow-x-auto" style={{ background: "var(--surface)" }}>
          <table className="w-full text-sm whitespace-nowrap">
            <thead>
              <tr style={{ borderBottom: "1px solid var(--border)" }}>
                {["Name", "Category", "Last status", "Location", "Serial", "Archived", ""].map((h) => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide"
                    style={{ color: "var(--text-secondary)" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {isLoading && <tr><td colSpan={7} className="px-4 py-8 text-center" style={{ color: "var(--text-secondary)" }}>Loading…</td></tr>}
              {!isLoading && !assets?.length && (
                <tr><td colSpan={7} className="px-4 py-10 text-center" style={{ color: "var(--text-secondary)" }}>No archived assets.</td></tr>
              )}
              {assets?.map((a) => (
                <tr key={a.id} style={{ borderBottom: "1px solid var(--border)" }}>
                  <td className="px-4 py-3 font-medium" style={{ color: "var(--text-primary)" }}>{a.name}</td>
                  <td className="px-4 py-3 capitalize" style={{ color: "var(--text-secondary)" }}>{a.category}</td>
                  <td className="px-4 py-3">
                    <span className="text-xs font-medium px-2 py-0.5 rounded-full"
                      style={{ color: STATUS_STYLE[a.status].color, background: `${STATUS_STYLE[a.status].color}1a` }}>
                      {STATUS_STYLE[a.status].label}
                    </span>
                  </td>
                  <td className="px-4 py-3" style={{ color: "var(--text-secondary)" }}>{a.location ?? "—"}</td>
                  <td className="px-4 py-3" style={{ color: "var(--text-secondary)" }}>{a.serial_number ?? "—"}</td>
                  <td className="px-4 py-3" style={{ color: "var(--text-secondary)" }}>
                    {a.archived_at ? new Date(a.archived_at).toLocaleDateString() : "—"}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex gap-1 justify-end">
                      <button onClick={() => setPassportFor(a)} title="Device passport (history)"
                        className="p-1 rounded-lg hover:bg-blue-500/10 hover:text-blue-500" style={{ color: "var(--text-secondary)" }}>
                        <History size={14} />
                      </button>
                      {isStaff && (
                        <button onClick={() => restore(a.id)} title="Restore to active register"
                          className="p-1 rounded-lg hover:bg-green-500/10 hover:text-green-500" style={{ color: "var(--text-secondary)" }}>
                          <RotateCcw size={14} />
                        </button>
                      )}
                      {isAdmin && (
                        <button onClick={() => removeForever(a.id, a.name)} title="Delete permanently (erases history)"
                          className="p-1 rounded-lg hover:bg-red-500/10 hover:text-red-500" style={{ color: "var(--text-secondary)" }}>
                          <Trash2 size={14} />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {passportFor && <AssetPassportDrawer asset={passportFor} onClose={() => setPassportFor(null)} />}
    </div>
  );
}
