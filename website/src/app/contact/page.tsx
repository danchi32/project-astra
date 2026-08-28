import type { Metadata } from "next";
import { ContactContent } from "./ContactContent";

export const metadata: Metadata = {
  title: "Contact",
  description:
    "Get in touch with Technomate IT-Solution for managed IT services, hardware, or a demo of ASTRA — our AI System Administrator.",
  alternates: { canonical: "/contact/" },
};

export default function ContactPage() {
  return <ContactContent />;
}
