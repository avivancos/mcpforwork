/**
 * Dashboard scope — everything under this group honors the system color
 * scheme (dark mappings from comps 4i/4j). Landing and docs stay light-only
 * by design, so the [data-allow-dark] hook lives here, not on <body>.
 */
export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div data-allow-dark style={{ minHeight: "100dvh", background: "var(--bg)", color: "var(--ink)" }}>
      {children}
    </div>
  );
}
