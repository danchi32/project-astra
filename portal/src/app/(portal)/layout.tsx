import { Sidebar } from "@/components/sidebar";

export default function PortalLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="flex-1 overflow-auto p-6" style={{ background: "var(--bg)" }}>
        {children}
      </main>
    </div>
  );
}
