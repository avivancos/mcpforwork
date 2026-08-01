"use client";

/**
 * Top-level error boundary. It replaces the root layout when a render throws at
 * the very top of the tree, so it must render its own <html>/<body>. Kept
 * dependency-free with inline styles (globals.css may not have loaded).
 */
export default function GlobalError({ reset }: { error: Error; reset: () => void }) {
  return (
    <html lang="en">
      <body
        style={{
          margin: 0,
          minHeight: "100dvh",
          background: "#fafaf9",
          color: "#1c1917",
          fontFamily: "ui-sans-serif, system-ui, sans-serif",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: 16,
          padding: 24,
          textAlign: "center",
        }}
      >
        <h1 style={{ fontSize: 24, fontWeight: 650, letterSpacing: "-0.01em", margin: 0 }}>Something went wrong</h1>
        <p style={{ fontSize: 15, color: "#57534e", lineHeight: 1.6, maxWidth: 440, margin: 0 }}>
          An unexpected error interrupted the page. Your data is safe. Try again in a moment.
        </p>
        <button
          type="button"
          onClick={reset}
          style={{
            background: "#4f46e5",
            color: "#fff",
            border: "none",
            padding: "11px 20px",
            borderRadius: 9,
            fontWeight: 600,
            fontSize: 14.5,
            cursor: "pointer",
          }}
        >
          Reload
        </button>
      </body>
    </html>
  );
}
