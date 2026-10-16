"use client";
import { Users } from "lucide-react";
import { TrackerTabs } from "../TrackerTabs";

/** Tracker > Teams. Departments of people, rolled up and measured against their shift.
 *
 *  Placeholder until the account→user→team mapping lands: today the Tracker keys on a Windows
 *  account (ACME\\rahul), not a directory user, so there is nothing to group by yet. The next
 *  slice builds that mapping and this becomes the team rollup. */
export default function TrackerTeamsPage() {
  return (
    <div className="space-y-6">
      <TrackerTabs active="teams" />
      <div
        className="rounded-2xl p-8 text-center"
        style={{ background: "var(--surface)", border: "1px solid var(--border)" }}
      >
        <div
          className="inline-flex p-3 rounded-xl mb-3"
          style={{ background: "rgba(154,47,187,0.1)", color: "var(--accent)" }}
        >
          <Users size={22} />
        </div>
        <h2 className="text-base font-semibold" style={{ color: "var(--text-primary)" }}>
          Team rollups are coming
        </h2>
        <p className="text-sm mt-1.5 max-w-md mx-auto" style={{ color: "var(--text-secondary)" }}>
          Attendance and productivity grouped by department, measured against each team&apos;s
          shift. This needs tracked Windows accounts mapped to people and teams — being set up
          next.
        </p>
      </div>
    </div>
  );
}
