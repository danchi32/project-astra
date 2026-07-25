import type { Metadata } from "next";
import { PricingContent } from "./PricingContent";

export const metadata: Metadata = {
  title: "Pricing",
  description:
    "Simple, per-user pricing for Astra — the AI System Administrator. Plans for teams of every size, with bulk pricing on request.",
  alternates: { canonical: "/pricing/" },
};

export default function PricingPage() {
  return <PricingContent />;
}
