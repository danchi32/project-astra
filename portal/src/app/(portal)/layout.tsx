"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Sidebar } from "@/components/sidebar";
import { ViewAsBanner } from "@/components/view-as-banner";

export default function PortalLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [authed, setAuthed] = useState<boolean | null>(null);

  // Auth gate: never paint protected pages without a token. Previously the page
  // rendered first and only bounced once an API call came back 401 — which briefly
  // exposed the screen to signed-out visitors deep-linking to /dashboard, /devices…
  useEffect(() => {
    const token =
      localStorage.getItem("view_as_token") || localStorage.getItem("access_token");
    if (!token) {
      router.replace("/login");
      setAuthed(false);
      return;
    }
    setAuthed(true);
  }, [router]);

  // Until the check resolves (and while redirecting), render an empty shell —
  // no protected content, no flash.
  if (authed !== true) {
    return <div className="h-screen" style={{ background: "var(--bg)" }} />;
  }

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <ViewAsBanner />
        <main className="flex-1 overflow-y-auto p-6" style={{ background: "var(--bg)" }}>
          {children}
        </main>
      </div>
    </div>
  );
}
