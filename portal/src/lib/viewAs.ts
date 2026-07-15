// "View as organization" — a platform admin browses one org's portal read-only.
// While active, a scoped view-as token overrides the normal access token for all
// API calls (see api/client.ts). State lives in localStorage so it survives reloads.

export interface ViewAsOrg {
  id: string;
  name: string;
}

export function getViewAs(): ViewAsOrg | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem("view_as_org");
  try {
    return raw ? (JSON.parse(raw) as ViewAsOrg) : null;
  } catch {
    return null;
  }
}

export function enterViewAs(token: string, org: ViewAsOrg): void {
  localStorage.setItem("view_as_token", token);
  localStorage.setItem("view_as_org", JSON.stringify(org));
  window.dispatchEvent(new Event("viewas-change"));
}

export function exitViewAs(): void {
  localStorage.removeItem("view_as_token");
  localStorage.removeItem("view_as_org");
  window.dispatchEvent(new Event("viewas-change"));
}
