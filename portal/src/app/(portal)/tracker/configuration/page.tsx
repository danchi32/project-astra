"use client";
import { TrackerTabs } from "../TrackerTabs";
import { CategoryConfig } from "../CategoryConfig";
import { ShiftConfig } from "../ShiftConfig";

/** Tracker > Configuration. The setup home: productivity categories and department shifts,
 *  with the rest of the Tracker's settings landing here as they ship. One page, sections
 *  stacked, so an admin configures the whole tool in one place. */
export default function TrackerConfigurationPage() {
  return (
    <div className="space-y-8">
      <TrackerTabs active="configuration" />
      <CategoryConfig />
      <div className="border-t" style={{ borderColor: "var(--border)" }} />
      <ShiftConfig />
    </div>
  );
}
