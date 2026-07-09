"use client";
import { Bell } from "lucide-react";
import { ComingSoon } from "@/components/coming-soon";

export default function NotificationsPage() {
  return (
    <ComingSoon
      icon={Bell}
      title="Notifications"
      description="Alert rules, email/Slack routing and an in-app notification centre."
      phase="Coming in Phase 6"
    />
  );
}
