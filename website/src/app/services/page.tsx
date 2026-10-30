import type { Metadata } from "next";
import { ServicesContent } from "./ServicesContent";

export const metadata: Metadata = {
  title: "Services",
  description:
    "Website development, app & custom software, IT hardware, Microsoft licenses, managed IT and AI IT operations — all from Technomate IT-Solution.",
  alternates: { canonical: "/services/" },
};

export default function ServicesPage() {
  return <ServicesContent />;
}
