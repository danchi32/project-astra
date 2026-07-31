"use client";
import { ExternalLink, FileText } from "lucide-react";
import type { Invoice, InvoiceStatus, Page } from "@/lib/api/types";
import { ScrollPanel, stickyHeadCell } from "@/components/scroll-panel";
import { Pagination } from "@/components/pagination";

const STATUS: Record<InvoiceStatus, { label: string; color: string }> = {
  draft: { label: "Draft", color: "#64748b" },
  open: { label: "Unpaid", color: "#f59e0b" },
  paid: { label: "Paid", color: "#10b981" },
  failed: { label: "Failed", color: "#ef4444" },
  refunded: { label: "Refunded", color: "#3b82f6" },
  void: { label: "Void", color: "#64748b" },
};

/** Minor units to a readable amount.
 *
 *  The API stores integers so nothing rounds on the way through; the only place a decimal
 *  point appears is here, at the edge, where it is being read rather than calculated with. */
export function formatMoney(cents: number, currency: string): string {
  try {
    return new Intl.NumberFormat(undefined, { style: "currency", currency }).format(cents / 100);
  } catch {
    // An unrecognised currency code should still render a number, not crash the table.
    return `${(cents / 100).toFixed(2)} ${currency}`;
  }
}

function period(i: Invoice): string {
  if (!i.period_start || !i.period_end) return "—";
  const d = (s: string) => new Date(s).toLocaleDateString(undefined, { day: "numeric", month: "short" });
  return `${d(i.period_start)} – ${d(i.period_end)}`;
}

/**
 * One invoice history table, used by both the organization's own billing page and the
 * operator's cross-org view. Same component so the two can't drift into showing different
 * facts about the same record.
 */
export function InvoiceTable({
  data,
  page,
  onPage,
  busy = false,
  showOrg = false,
}: {
  data: Page<Invoice> | undefined;
  page: number;
  onPage: (n: number) => void;
  busy?: boolean;
  /** The operator's view adds an organization column; an org looking at its own history
   *  already knows whose invoices these are. */
  showOrg?: boolean;
}) {
  const rows = data?.items ?? [];
  const cols = [
    "Invoice", ...(showOrg ? ["Organization"] : []),
    "Issued", "Period", "Plan", "Amount", "Status", "",
  ];

  return (
    <ScrollPanel
      footer={<Pagination page={page} onPage={onPage} data={data} noun="invoice" busy={busy} />}
    >
      <table className="w-full text-sm whitespace-nowrap">
        <thead>
          <tr>
            {cols.map((h, i) => (
              <th key={h || i} className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide"
                style={stickyHeadCell}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 && (
            <tr>
              <td colSpan={cols.length} className="px-4 py-12 text-center">
                <FileText size={26} className="mx-auto mb-2" style={{ color: "var(--accent)", opacity: 0.4 }} />
                <p className="text-sm" style={{ color: "var(--text-primary)" }}>No invoices yet</p>
                <p className="text-xs mt-1" style={{ color: "var(--text-secondary)" }}>
                  They appear here as each billing period is charged.
                </p>
              </td>
            </tr>
          )}
          {rows.map((i) => (
            <tr key={i.id} style={{ borderBottom: "1px solid var(--border)" }}>
              <td className="px-4 py-3 font-medium" style={{ color: "var(--text-primary)" }}>{i.number}</td>
              {showOrg && (
                <td className="px-4 py-3" style={{ color: "var(--text-secondary)" }}>{i.org_name ?? "—"}</td>
              )}
              <td className="px-4 py-3" style={{ color: "var(--text-secondary)" }}>
                {new Date(i.issued_on).toLocaleDateString()}
              </td>
              <td className="px-4 py-3" style={{ color: "var(--text-secondary)" }}>{period(i)}</td>
              <td className="px-4 py-3 capitalize" style={{ color: "var(--text-secondary)" }}>{i.plan ?? "—"}</td>
              <td className="px-4 py-3 tabular-nums" style={{ color: "var(--text-primary)" }}>
                {formatMoney(i.total_cents, i.currency)}
                {i.tax_cents > 0 && (
                  <span className="text-xs ml-1" style={{ color: "var(--text-secondary)" }}>
                    incl. {formatMoney(i.tax_cents, i.currency)} tax
                  </span>
                )}
              </td>
              <td className="px-4 py-3">
                <span className="text-xs font-medium px-2 py-0.5 rounded-full"
                  style={{ color: STATUS[i.status].color, background: `${STATUS[i.status].color}1a` }}>
                  {STATUS[i.status].label}
                </span>
              </td>
              <td className="px-4 py-3 text-right">
                {/* Present only when the payment rail is the seller of record and issues the
                    document itself. Where it's absent ASTRA is the seller and the document
                    is generated — which isn't built yet, so nothing is offered rather than a
                    button that 404s. */}
                {i.provider_invoice_url ? (
                  <a href={i.provider_invoice_url} target="_blank" rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-xs px-2.5 py-1.5 rounded-lg"
                    style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--accent)" }}>
                    <ExternalLink size={12} /> Invoice
                  </a>
                ) : (
                  <span className="text-xs" style={{ color: "var(--text-secondary)" }}>—</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </ScrollPanel>
  );
}
