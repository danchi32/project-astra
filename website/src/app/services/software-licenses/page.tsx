import type { Metadata } from "next";
import { LicensesContent } from "./LicensesContent";

export const metadata: Metadata = {
  title: "Software & Licenses — Microsoft 365, Windows 11 Pro, Windows Server",
  description:
    "Genuine Microsoft 365 (Business Basic, Standard, Premium), Windows 11 Pro, Windows Server 2025, SQL Server, Office 2024 and more — licensed, deployed and renewed by Technomate IT-Solution.",
  alternates: { canonical: "/services/software-licenses/" },
};

export default function SoftwareLicensesPage() {
  return <LicensesContent />;
}
