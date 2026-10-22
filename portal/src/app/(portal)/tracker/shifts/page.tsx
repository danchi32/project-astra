"use client";
import { TrackerHeader } from "../TrackerHeader";
import { ShiftConfig } from "../ShiftConfig";

/** Tracker > Shifts. Department shift definitions and per-team assignment. */
export default function TrackerShiftsPage() {
  return (
    <div className="space-y-6">
      <TrackerHeader title="Shifts" subtitle="Department working hours and per-team assignment" />
      <ShiftConfig />
    </div>
  );
}
