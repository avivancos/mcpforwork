/**
 * Docs navigation config — the single source for the sidebar, active-state, and
 * prev/next. `available: false` items render as "coming soon" (no dead links);
 * they're seeded as follow-up card W2.2 (Reference + Self-hosting).
 */
/**
 * Every docs route path. Typing slugs as this union (not `string`) makes a
 * typo in a page's `slug=` prop a compile error instead of silently dropping
 * its breadcrumb + prev/next. Add new pages here when building W2.2.
 */
export type DocSlug =
  | "/docs"
  | "/docs/connect-claude"
  | "/docs/connect-chatgpt"
  | "/docs/build-your-profile"
  | "/docs/facts-inventory"
  | "/docs/regional-packs"
  | "/docs/consent-levels"
  | "/docs/scoring"
  | "/docs/dedup-tracking"
  | "/docs/mcp-tools"
  | "/docs/slash-commands"
  | "/docs/configuration"
  | "/docs/digest-email"
  | "/docs/install"
  | "/docs/data-backups"
  | "/docs/contribute-a-pack";

export interface DocItem {
  name: string;
  slug: DocSlug; // route path, e.g. "/docs/facts-inventory"
  available?: boolean; // default true; false = "coming soon"
  count?: number;
}

export interface DocGroup {
  label: string;
  items: DocItem[];
}

export const DOCS_NAV: DocGroup[] = [
  {
    label: "Getting started",
    items: [
      { name: "Quickstart", slug: "/docs" },
      { name: "Connect to Claude", slug: "/docs/connect-claude" },
      { name: "Connect to ChatGPT", slug: "/docs/connect-chatgpt" },
      { name: "Build your profile", slug: "/docs/build-your-profile" },
    ],
  },
  {
    label: "Core concepts",
    items: [
      { name: "Facts inventory", slug: "/docs/facts-inventory" },
      { name: "Regional packs", slug: "/docs/regional-packs" },
      { name: "Consent levels (L0–L2)", slug: "/docs/consent-levels" },
      { name: "Scoring & constraints", slug: "/docs/scoring" },
      { name: "Dedup & tracking", slug: "/docs/dedup-tracking" },
    ],
  },
  {
    label: "Reference",
    items: [
      { name: "MCP tools", slug: "/docs/mcp-tools", count: 38 },
      { name: "Slash commands", slug: "/docs/slash-commands" },
      { name: "Configuration", slug: "/docs/configuration" },
      { name: "Digest email", slug: "/docs/digest-email" },
    ],
  },
  {
    label: "Self-hosting",
    items: [
      { name: "Install & run", slug: "/docs/install" },
      { name: "Data & backups", slug: "/docs/data-backups" },
      { name: "Contribute a pack", slug: "/docs/contribute-a-pack" },
    ],
  },
];

/** Flat, ordered list of built pages — drives prev/next. */
export const DOCS_ORDER: DocItem[] = DOCS_NAV.flatMap((g) => g.items).filter((i) => i.available !== false);

export function docGroupOf(slug: string): string | undefined {
  return DOCS_NAV.find((g) => g.items.some((i) => i.slug === slug))?.label;
}

export function docNeighbors(slug: string): { prev?: DocItem; next?: DocItem } {
  const i = DOCS_ORDER.findIndex((d) => d.slug === slug);
  if (i < 0) return {};
  return { prev: DOCS_ORDER[i - 1], next: DOCS_ORDER[i + 1] };
}
