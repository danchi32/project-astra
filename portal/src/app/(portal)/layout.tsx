import { Sidebar } from "@/components/sidebar";
import { ViewAsBanner } from "@/components/view-as-banner";

export default function PortalLayout({ children }: { children: React.ReactNode }) {
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
