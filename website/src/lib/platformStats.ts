"use client";

import { useEffect, useState } from "react";

import { site } from "@/lib/site";

/**
 * Live counts from the ASTRA platform, for the homepage.
 *
 * The four figures in the hero used to be written by hand — 1,204+ issues auto-healed,
 * 38s average resolution, 72% less manual triage, 99.9% fleet visibility — and none of
 * them was ever measured. Numbers that nobody maintains drift from true to false the day
 * they are typed. These come from the platform, so they cannot.
 *
 * The site is a static export with no server of its own, so this reads the API straight
 * from the visitor's browser, the same way the support chat does. The endpoint is public,
 * returns aggregate counts only, and excludes our own internal workspace.
 */

const API = process.env.NEXT_PUBLIC_ASTRA_API_URL || site.apiUrl;

export type PlatformStats = {
  organizations: number;
  devices: number;
  devices_online: number;
  remediations: number;
  remediation_actions: number;
  generated_at: string;
};

export type StatsState =
  | { status: "loading" }
  | { status: "ready"; stats: PlatformStats }
  | { status: "unavailable" };

export function usePlatformStats(): StatsState {
  const [state, setState] = useState<StatsState>({ status: "loading" });

  useEffect(() => {
    // Abort on unmount so a slow response cannot set state on a gone component, and so a
    // visitor who leaves immediately does not hold the request open.
    const controller = new AbortController();

    (async () => {
      try {
        const response = await fetch(`${API}/api/v1/public/stats`, {
          signal: controller.signal,
        });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        setState({ status: "ready", stats: (await response.json()) as PlatformStats });
      } catch {
        // Deliberately silent, and deliberately NOT a fallback to zeros. A hero reading
        // "0 devices under management" is worse than one that shows nothing at all: the
        // first is a claim, the second is an absence. The caller hides the block.
        if (!controller.signal.aborted) setState({ status: "unavailable" });
      }
    })();

    return () => controller.abort();
  }, []);

  return state;
}

/**
 * The stat cards, built from live counts.
 *
 * Three cumulative figures and one product fact. All four come from the platform, so none
 * of them is maintained by hand and none can go stale.
 *
 * `devices_online` is deliberately NOT among them, even though the endpoint returns it.
 * The other three only ever go up and describe what has happened; a liveness reading
 * swings with the clock and the calendar. It read 0 the Saturday this was written — 34
 * devices enrolled, offices closed — and would have read about 34 the following Tuesday.
 * Nothing about the product would have changed. On a page strangers read at all hours,
 * that number reports on whether offices are open, and the failure is asymmetric: nobody
 * remembers the 34, everybody remembers the 0. It belongs in the fleet dashboard, where a
 * live reading is the point and the viewer knows what they are looking at.
 */
export function statCards(stats: PlatformStats) {
  return [
    { value: stats.organizations, suffix: "", label: "Organizations onboarded" },
    { value: stats.devices, suffix: "", label: "Devices under management" },
    { value: stats.remediations, suffix: "", label: "Issues auto-healed" },
    { value: stats.remediation_actions, suffix: "", label: "Remediation actions" },
  ];
}
