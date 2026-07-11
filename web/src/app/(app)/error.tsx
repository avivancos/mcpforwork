"use client";

/**
 * Error boundary for the whole app group. Once the HTTP adapter is live, a
 * transient fetch failure in a render or a server action surfaces here as a
 * calm, retryable message instead of Next's default unstyled crash page.
 */
export default function AppError({ reset }: { error: Error; reset: () => void }) {
  return (
    <div
      data-allow-dark
      style={{
        minHeight: "100dvh",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: 16,
        padding: 24,
        textAlign: "center",
        background: "var(--bg)",
        color: "var(--ink)",
      }}
    >
      <h1 style={{ fontSize: 22, fontWeight: 650, letterSpacing: "-0.01em" }}>Something went wrong</h1>
      <p style={{ fontSize: 14, color: "var(--ink-2)", maxWidth: 420, lineHeight: 1.55 }}>
        We couldn&rsquo;t load this view. Your data is safe — nothing was changed. Try again in a
        moment.
      </p>
      <button type="button" className="btn btn--primary" onClick={reset}>
        Retry
      </button>
    </div>
  );
}
