"use client";
import { TrackerHeader } from "../TrackerHeader";
import { CategoryConfig } from "../CategoryConfig";
import { AttendanceConfig } from "../AttendanceConfig";

/** Tracker > Configuration. The attendance calendar (working days, thresholds, holidays) and
 *  what counts as productive (Categories). Who each account is comes from the device's Assets
 *  assignment, so there is no account→person mapping here; Shifts have their own section. */
export default function TrackerConfigurationPage() {
  return (
    <div className="space-y-8">
      <TrackerHeader title="Configuration" subtitle="Attendance rules and productivity categories" />
      <AttendanceConfig />
      <div className="border-t" style={{ borderColor: "var(--border)" }} />
      <CategoryConfig />
    </div>
  );
}
