import type { Metadata } from "next";
import { HomeContent } from "./HomeContent";

export const metadata: Metadata = {
  // Home-specific description (more targeted than the site default).
  description:
    "Managed IT services, business laptops & hardware, and ASTRA — an AI System Administrator that watches every device, diagnoses issues and self-heals your Windows fleet with human approval where it matters.",
  alternates: { canonical: "/" },
};

export default function HomePage() {
  return <HomeContent />;
}
