export default function SettingsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>Settings</h1>
        <p className="text-sm mt-0.5" style={{ color: "var(--text-secondary)" }}>
          Organization and platform configuration
        </p>
      </div>
      <div className="rounded-xl p-8 text-center" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
        <p style={{ color: "var(--text-secondary)" }}>Settings module — Phase 6</p>
      </div>
    </div>
  );
}
