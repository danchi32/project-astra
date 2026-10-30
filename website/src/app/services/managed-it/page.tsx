import type { Metadata } from "next";
import { ManagedItContent } from "./ManagedItContent";

export const metadata: Metadata = {
  title: "Managed IT Services — Helpdesk, Monitoring & Security",
  description:
    "Managed IT services from Technomate IT-Solution: helpdesk and on-site support, patching, 24/7 monitoring, backups, security, networks and user onboarding — one monthly plan, powered by SAVIO.",
  alternates: { canonical: "/services/managed-it/" },
};

export default function ManagedItPage() {
  return <ManagedItContent />;
}
