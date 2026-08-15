"use client";
import Link from "next/link";
import { ChevronLeft, Download, LifeBuoy } from "lucide-react";
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

      {/* Installation is where people get stuck, and someone stuck here is not going to go
          looking through a sidebar for the word "help". */}
      <div
        className="rounded-xl p-4 flex items-center justify-between gap-3 flex-wrap"
        style={{ background: "var(--surface)", border: "1px solid var(--border)" }}
      >
        <div className="flex items-center gap-2.5">
          <LifeBuoy size={17} style={{ color: "var(--text-secondary)" }} />
          <div>
            <p className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>
              Install not working?
            </p>
            <p className="text-xs mt-0.5" style={{ color: "var(--text-secondary)" }}>
              Search the guides by the error code you saw, or ask the ASTRA team.
            </p>
          </div>
        </div>
        <Link
          href="/help"
          className="px-3 py-2 rounded-lg text-sm font-medium shrink-0"
          style={{ border: "1px solid var(--border)", color: "var(--accent)" }}
        >
          Open help &amp; support
        </Link>
      </div>
    </div>
  );
}
