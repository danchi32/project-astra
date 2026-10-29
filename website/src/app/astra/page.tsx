import type { Metadata } from "next";
import { Redirect } from "@/components/Redirect";

// The product page moved here → /savio/ when ASTRA was renamed SAVIO.
export const metadata: Metadata = {
  title: "SAVIO — AI System Administrator",
  robots: { index: false, follow: true },
  alternates: { canonical: "/savio/" },
};

export default function AstraMoved() {
  return <Redirect to="/savio/" />;
}
