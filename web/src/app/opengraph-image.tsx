import { ImageResponse } from "next/og";

// Branded 1200×630 share card, rendered by next/og (built into Next — no dep).
export const alt = "mcpfor.work — your AI already knows how to job-hunt";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OpengraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          background: "#EDEBE6",
          padding: "72px 80px",
        }}
      >
        <div style={{ display: "flex", alignItems: "baseline", fontSize: 34, fontWeight: 600, letterSpacing: "-0.01em" }}>
          <span style={{ color: "#4F46E5" }}>mcp</span>
          <span style={{ color: "#1C1917" }}>for.work</span>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              fontSize: 76,
              fontWeight: 700,
              lineHeight: 1.05,
              letterSpacing: "-0.03em",
              color: "#1C1917",
              maxWidth: 1000,
            }}
          >
            Your AI already knows how to job-hunt.&nbsp;<span style={{ color: "#4F46E5" }}>Give it hands.</span>
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", fontSize: 26, color: "#57534E" }}>
          <span>Open source</span>
          <span style={{ color: "#A8A29E", padding: "0 14px" }}>·</span>
          <span>$5/mo</span>
          <span style={{ color: "#A8A29E", padding: "0 14px" }}>·</span>
          <span>Zero server-side LLM calls</span>
        </div>
      </div>
    ),
    { ...size },
  );
}
