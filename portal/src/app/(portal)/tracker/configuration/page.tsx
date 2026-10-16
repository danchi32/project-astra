"use client";
import { TrackerTabs } from "../TrackerTabs";
import { CategoryConfig } from "../CategoryConfig";

/** Tracker > Configuration. The setup home: productivity categories today, with shifts and the
 *  rest of the Tracker's settings landing here as they ship. One page, sections stacked, so an
 *  admin configures the whole tool in one place. */
export default function TrackerConfigurationPage() {
  return (
    <div className="space-y-6">
      <TrackerTabs active="configuration" />
      <CategoryConfig />
    </div>
  );
}
