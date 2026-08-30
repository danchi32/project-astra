import type { Metadata } from "next";
import { HomeContent } from "./HomeContent";

export const metadata: Metadata = {
  title: "AI-Powered Managed IT & Self-Healing Windows Support",
  // Home-specific description (more targeted than the site default).
  description:
    "Reduce IT tickets with managed support and ASTRA, the AI system administrator for Windows fleets. Live telemetry, controlled self-healing, patching and human approvals.",
  alternates: { canonical: "/" },
};

export default function HomePage() {
  return <HomeContent />;
}
