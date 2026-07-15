import { Sidebar } from "@/components/sidebar";
import { ViewAsBanner } from "@/components/view-as-banner";

export default function PortalLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <ViewAsBanner />
        <main className="flex-1 overflow-auto p-6" style={{ background: "var(--bg)" }}>
          {children}
        </main>
      </div>
    </div>
  );
}
