"use client";
import { TrackerHeader } from "../TrackerHeader";
import { CategoryConfig } from "../CategoryConfig";
import { AccountConfig } from "../AccountConfig";

/** Tracker > Configuration. Who each tracked account is (People) and what counts as productive
 *  (Categories). Shifts have their own section now. */
export default function TrackerConfigurationPage() {
  return (
    <div className="space-y-8">
      <TrackerHeader title="Configuration" subtitle="Map accounts to people and tune productivity categories" />
      <AccountConfig />
      <div className="border-t" style={{ borderColor: "var(--border)" }} />
      <CategoryConfig />
    </div>
  );
}
