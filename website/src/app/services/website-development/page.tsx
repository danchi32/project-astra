import type { Metadata } from "next";
import { WebsiteContent } from "./WebsiteContent";

export const metadata: Metadata = {
  title: "Website Development & Ready Templates",
  description:
    "Modern, mobile-first business websites from Technomate IT-Solution. Preview ready-made templates for corporate, e-commerce, restaurant, real estate, clinic, school, agency and SaaS sites.",
  alternates: { canonical: "/services/website-development/" },
};

export default function WebsiteDevelopmentPage() {
  return <WebsiteContent />;
}
