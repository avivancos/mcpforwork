import Link from "next/link";
import { Logo } from "@/components/Logo";

export const metadata = { title: "Not found — mcpfor.work" };

export default function NotFound() {
  return (
    <div
      style={{
        minHeight: "100dvh",
        background: "var(--bg)",
        color: "var(--ink)",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: 20,
        padding: 24,
        textAlign: "center",
      }}
    >
      <Logo size={16} />
      <div style={{ fontFamily: "var(--font-mono)", fontSize: 13, letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--ink-3)" }}>
        404
      </div>
      <h1 style={{ fontSize: 34, fontWeight: 650, letterSpacing: "-0.02em", margin: 0 }}>This page went hunting</h1>
      <p style={{ fontSize: 15, color: "var(--ink-2)", lineHeight: 1.6, maxWidth: 440 }}>
        We couldn&rsquo;t find that page. Try the docs, or head back to the start.
      </p>
      <div style={{ display: "flex", gap: 12, marginTop: 4, flexWrap: "wrap", justifyContent: "center" }}>
        <Link
          href="/"
          style={{ background: "var(--accent-strong)", color: "#fff", padding: "11px 20px", borderRadius: 9, fontWeight: 600, fontSize: 14.5 }}
        >
          Home
        </Link>
        <Link
          href="/docs"
          style={{ border: "1px solid var(--border-input)", padding: "10px 18px", borderRadius: 9, fontWeight: 500, fontSize: 14, background: "var(--card)", color: "var(--ink)" }}
        >
          Read the docs
        </Link>
      </div>
    </div>
  );
}
