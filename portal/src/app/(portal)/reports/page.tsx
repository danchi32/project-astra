"use client";
import { BarChart3 } from "lucide-react";
import { ComingSoon } from "@/components/coming-soon";

export default function ReportsPage() {
  return (
    <ComingSoon
      icon={BarChart3}
      title="Reports"
      description="Scheduled fleet-health reports, SLA summaries and exportable analytics."
      phase="Coming in Phase 6"
    />
  );
}
