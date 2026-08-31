import type { Metadata } from "next";
import { AstraContent } from "./AstraContent";
import { AstraJsonLd } from "@/components/JsonLd";

export const metadata: Metadata = {
  title: "AI System Administrator for Windows | ASTRA",
  description:
    "ASTRA is AI System Administrator software for Windows fleets. Diagnose endpoint issues, run governed fixes, and verify results with human approval controls.",
  keywords: [
    "AI System Administrator",
    "AI System Admin",
    "AI sysadmin",
    "AI IT administrator",
    "automated system administration",
    "Windows IT automation",
  ],
  alternates: { canonical: "/astra/" },
};

export default function AstraPage() {
  return (
    <>
      <AstraJsonLd />
      <AstraContent />
    </>
  );
}
