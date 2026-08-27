import type { Metadata } from "next";
import { PricingContent } from "./PricingContent";

export const metadata: Metadata = {
  title: "Pricing",
  description:
    "Simple, per-device pricing for ASTRA — the AI System Administrator. Essential, Professional and Expert plans, with volume pricing on request.",
  alternates: { canonical: "/pricing/" },
};

export default function PricingPage() {
  return <PricingContent />;
}
