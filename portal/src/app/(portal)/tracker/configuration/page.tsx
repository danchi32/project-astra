"use client";
import { TrackerTabs } from "../TrackerTabs";
import { CategoryConfig } from "../CategoryConfig";
import { ShiftConfig } from "../ShiftConfig";
import { AccountConfig } from "../AccountConfig";

/** Tracker > Configuration. The setup home: who each tracked account is (People), what counts
 *  as productive (Categories), and each department's hours (Shifts). One page, sections stacked,
 *  so an admin configures the whole tool in one place. */
export default function TrackerConfigurationPage() {
  return (
    <div className="space-y-8">
      <TrackerTabs active="configuration" />
      <AccountConfig />
      <div className="border-t" style={{ borderColor: "var(--border)" }} />
      <CategoryConfig />
      <div className="border-t" style={{ borderColor: "var(--border)" }} />
      <ShiftConfig />
    </div>
  );
}
