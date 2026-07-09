"use client";
import { Package } from "lucide-react";
import { ComingSoon } from "@/components/coming-soon";

export default function AssetsPage() {
  return (
    <ComingSoon
      icon={Package}
      title="Assets"
      description="Warranty tracking, asset lifecycle, license management and procurement."
      phase="Coming in Phase 6 — use Devices for the current hardware inventory."
    />
  );
}
