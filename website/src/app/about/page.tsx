import type { Metadata } from "next";
import { AboutContent } from "./AboutContent";

export const metadata: Metadata = {
  title: "About Us",
  description:
    "Technomate IT Solution is an IT service provider and hardware supplier, delivering managed IT, laptops and business hardware — now powered by Astra AI.",
  alternates: { canonical: "/about/" },
};

export default function AboutPage() {
  return <AboutContent />;
}
