import type { Metadata } from "next";
import { AppContent } from "./AppContent";

export const metadata: Metadata = {
  title: "App & Custom Software Development",
  description:
    "Android, iOS and web apps plus custom business software — field service, e-commerce, clinic booking, inventory, HR and school apps by Technomate IT-Solution.",
  alternates: { canonical: "/services/app-development/" },
};

export default function AppDevelopmentPage() {
  return <AppContent />;
}
