/**
 * Canonical site origin — the single source for metadataBase, robots, sitemap,
 * and the manifest. Override per deploy with NEXT_PUBLIC_SITE_URL.
 */
export const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "https://mcpfor.work";

export const SITE_NAME = "mcpfor.work";

export const SITE_TITLE = "mcpfor.work — your AI already knows how to job-hunt";

export const SITE_DESCRIPTION =
  "Open-source, MCP-first job-search copilot. Connect the Claude or ChatGPT you already pay for to real job portals — in your browser, in your voice, under your control. Zero server-side LLM calls.";
