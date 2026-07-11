import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Self-contained server bundle for a lean Docker runtime image (only the
  // traced deps ship, not all of node_modules). See docker/ + ADR 0003.
  output: "standalone",
  // Pin the file-tracing root to this app: a stray lockfile higher up the
  // tree otherwise makes Next infer the wrong workspace root.
  outputFileTracingRoot: __dirname,
  // No other options — defaults only. Additions need a justification line on
  // the card (anti-over-engineering charter).
};

export default nextConfig;
