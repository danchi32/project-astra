import type { Metadata } from "next";
import { HardwareContent } from "./HardwareContent";

export const metadata: Metadata = {
  title: "IT Hardware & Assets — Laptops, Servers, Firewalls",
  description:
    "Business laptops, desktops, workstations, servers, NAS, firewalls, switches, Wi-Fi, printers, UPS and CCTV — sourced, configured and delivered by Technomate IT-Solution.",
  alternates: { canonical: "/services/it-hardware/" },
};

export default function ItHardwarePage() {
  return <HardwareContent />;
}
