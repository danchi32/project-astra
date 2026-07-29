"use client";
import Link from "next/link";
import { ChevronLeft, Download } from "lucide-react";
import { InstallAgentPanel } from "@/components/install-agent-panel";

export default function InstallPage() {
  return (
    <div className="space-y-4 max-w-3xl">
      <Link href="/devices" className="inline-flex items-center gap-1 text-sm" style={{ color: "var(--accent)" }}>
        <ChevronLeft size={15} /> Devices
      </Link>
      <div className="flex items-center gap-2">
        <div className="p-2 rounded-lg" style={{ background: "rgba(154,47,187,0.1)", color: "var(--accent)" }}>
          <Download size={18} />
        </div>
        <div>
          <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>Get the installer</h1>
          <p className="text-sm mt-0.5" style={{ color: "var(--text-secondary)" }}>
            Deploy the ASTRA agent to a Windows machine — your enrollment key is already baked in.
          </p>
        </div>
      </div>
      <InstallAgentPanel defaultOpen />
    </div>
  );
}
