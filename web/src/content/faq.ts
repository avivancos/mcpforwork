/**
 * Single source for FAQ content — used by both the landing section and the
 * standalone /faq page, so they never drift.
 */
export interface FaqItem {
  q: string;
  a: string;
}
export interface FaqGroup {
  label: string;
  items: FaqItem[];
}

export const FAQ_GROUPS: FaqGroup[] = [
  {
    label: "How it works",
    items: [
      {
        q: "Do I need an API key?",
        a: "No. Your Claude or ChatGPT subscription is the brain. We never proxy, meter, or bill tokens.",
      },
      {
        q: "Does it apply without me?",
        a: "Only if you turn Autopilot (L2) on, under a policy you set: minimum score, daily cap, allowlisted sites. The default is L0 — you click Submit.",
      },
      {
        q: "What about captchas?",
        a: "You solve them. It never bypasses or automates a captcha — applications run in your own browser session.",
      },
      {
        q: "Which AI clients work?",
        a: "Claude connectors, Claude Desktop (.mcpb), Claude Code, ChatGPT connectors, and the Codex CLI. One account, both ecosystems.",
      },
    ],
  },
  {
    label: "Privacy & data",
    items: [
      {
        q: "Where is my data?",
        a: "Self-hosted: it never leaves your machine. Hosted: export everything as JSON or delete your account, any time. GDPR-clean.",
      },
      {
        q: "Do you train on my data?",
        a: "No. We run zero server-side LLM calls — there is no model on our side to train. Your data is used only to run your own job search.",
      },
      {
        q: "Is my salary floor shared?",
        a: "Never disclosed without your consent. It's a private field, used only to filter matches.",
      },
      {
        q: "Is self-host the full product?",
        a: "Yes — open-core parity. Same features on your machine with SQLite. The hosted plan buys convenience, not capability.",
      },
    ],
  },
  {
    label: "Pricing",
    items: [
      {
        q: "Is there a free trial?",
        a: "Yes — 7 days, no card required to start. After that it's a single flat plan at $5/month. No tiers, no seats.",
      },
      {
        q: "Why only $5?",
        a: "Because $5 pays for infrastructure — sync, backups, live pack updates. Not token resale. Your AI does the expensive part.",
      },
      {
        q: "Can I cancel anytime?",
        a: "Any time, from your billing settings — and you can export or delete all your data on the way out.",
      },
    ],
  },
];

/** Flattened list for the landing's compact section. */
export const FAQ_FLAT: FaqItem[] = FAQ_GROUPS.flatMap((g) => g.items);
