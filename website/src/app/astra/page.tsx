import type { Metadata } from "next";
import { AstraContent } from "./AstraContent";
import { AstraJsonLd } from "@/components/JsonLd";

export const metadata: Metadata = {
  title: "Astra — Your AI System Administrator",
  description:
    "Astra is an AI System Administrator that automates IT support: asset inventory, live telemetry, AI reasoning, and tiered self-healing across your entire Windows fleet.",
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
