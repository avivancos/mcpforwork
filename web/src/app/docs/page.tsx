import Link from "next/link";
import { CopyButton } from "@/components/CopyButton";
import { Logo } from "@/components/Logo";
import styles from "./docs.module.css";

export const metadata = { title: "Quickstart — mcpfor.work docs" };

const SIDEBAR: { label: string; items: { name: string; active?: boolean; count?: number }[] }[] = [
  {
    label: "Getting started",
    items: [
      { name: "Quickstart", active: true },
      { name: "Connect to Claude" },
      { name: "Connect to ChatGPT" },
      { name: "Build your profile" },
    ],
  },
  {
    label: "Core concepts",
    items: [
      { name: "Facts inventory" },
      { name: "Regional packs" },
      { name: "Consent levels (L0–L2)" },
      { name: "Scoring & constraints" },
      { name: "Dedup & tracking" },
    ],
  },
  {
    label: "Reference",
    items: [
      { name: "MCP tools", count: 14 },
      { name: "Slash commands" },
      { name: "Configuration" },
      { name: "Digest email" },
    ],
  },
  {
    label: "Self-hosting",
    items: [{ name: "Install & run" }, { name: "Data & backups" }, { name: "Contribute a pack" }],
  },
];

const CONFIG_SNIPPET = `{
  "mcpServers": {
    "mcpforwork": { "command": "uvx", "args": ["mcpforwork"] }
  }
}`;

export default function DocsPage() {
  return (
    <div className={styles.page}>
      <div className={styles.container}>
        <nav className={styles.nav}>
          <div className={styles.navLeft}>
            <Logo />
            <span className={styles.docsBadge}>Docs</span>
          </div>
          <div className={styles.search} aria-hidden>
            <span>Search docs…</span>
            <span className={styles.kbd}>⌘K</span>
          </div>
          <div className={styles.navRight}>
            <a href="https://github.com/mcpforwork">GitHub</a>
            <Link href="/pipeline" className={styles.dashBtn}>
              Dashboard
            </Link>
          </div>
        </nav>

        <div className={styles.grid}>
          {/* sidebar */}
          <aside className={styles.sidebar} aria-label="Docs navigation">
            {SIDEBAR.map((group) => (
              <div key={group.label} className={styles.group}>
                <span className={styles.groupLabel}>{group.label}</span>
                {group.items.map((item) => (
                  <a
                    key={item.name}
                    href="#"
                    className={`${styles.item} ${item.active ? styles.itemActive : ""}`}
                    aria-current={item.active ? "page" : undefined}
                  >
                    {item.name}
                    {item.count !== undefined && <span className={styles.count}>{item.count}</span>}
                  </a>
                ))}
              </div>
            ))}
          </aside>

          {/* content */}
          <main className={styles.content}>
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              <span className={styles.breadcrumb}>
                Getting started <span style={{ color: "var(--border-input)" }}>/</span> <b>Quickstart</b>
              </span>
              <h1 className={styles.h1}>Quickstart</h1>
              <p className={styles.lead}>
                From zero to your first supervised application in about five minutes. You&rsquo;ll
                need a Claude or ChatGPT subscription — no API key.
              </p>
            </div>

            <section className={styles.section} id="docs-install">
              <h2 className={styles.h2}>1. Install</h2>
              <p className={styles.p}>
                Run the server locally with <span className={styles.inlineCode}>uvx</span> — no
                clone, no build step. It creates a local SQLite database on first run.
              </p>
              <div className="term">
                <div className="term__bar">
                  <span>terminal</span>
                  <CopyButton text="uvx mcpforwork" className="term__copy" />
                </div>
                <div className="term__body">
                  <div>
                    <span className="p">$</span> uvx mcpforwork
                  </div>
                  <div className="a">✓ mcpfor.work v0.4.2 · sqlite: ~/.mcpforwork/data.db</div>
                  <div className="a">✓ MCP server listening on stdio</div>
                </div>
              </div>
            </section>

            <section className={styles.section} id="docs-connect">
              <h2 className={styles.h2}>2. Connect your AI</h2>
              <p className={styles.p}>
                Add the server to Claude Desktop. Hosted users skip this — connect from claude.ai in
                one click.
              </p>
              <div className="term">
                <div className="term__bar">
                  <span>claude_desktop_config.json</span>
                  <CopyButton text={CONFIG_SNIPPET} className="term__copy" />
                </div>
                <div className="term__body">
                  <div>{"{"}</div>
                  <div>
                    &nbsp;&nbsp;<span className="a">&quot;mcpServers&quot;</span>: {"{"}
                  </div>
                  <div>
                    &nbsp;&nbsp;&nbsp;&nbsp;<span className="a">&quot;mcpforwork&quot;</span>: {"{"}{" "}
                    <span className="a">&quot;command&quot;</span>: <span className="s">&quot;uvx&quot;</span>,{" "}
                    <span className="a">&quot;args&quot;</span>: [<span className="s">&quot;mcpforwork&quot;</span>] {"}"}
                  </div>
                  <div>&nbsp;&nbsp;{"}"}</div>
                  <div>{"}"}</div>
                </div>
              </div>
            </section>

            <section className={styles.section} id="docs-profile">
              <h2 className={styles.h2}>3. Build your profile</h2>
              <p className={styles.p}>
                Give it your CV and answer a short interview. This builds your{" "}
                <strong style={{ fontWeight: 600 }}>facts inventory</strong> — the only source drafts
                may claim from — plus your hard constraints (visa, salary floor, language).
              </p>
              <div className={styles.chatSample}>
                <span className={styles.chatUser}>/profile — here&rsquo;s my CV (attached)</span>
                <span className={styles.chatBot}>
                  Extracted 18 facts from your CV. Three quick questions: what&rsquo;s your salary
                  floor? (stays private, only filters matches)
                </span>
              </div>
            </section>

            <section className={styles.section} id="docs-hunt">
              <h2 className={styles.h2}>4. Hunt and apply</h2>
              <p className={styles.p}>
                Ask your AI to hunt. It browses portals in your browser, scores matches against your
                constraints, drafts from your facts — and pauses at Submit.
              </p>
              <div className="term">
                <div className="term__bar">
                  <span>Claude</span>
                </div>
                <div className="term__body">
                  <div>
                    <span className="p">›</span> /hunt icu nurse dublin
                  </div>
                  <div className="a">12 found · 3 new · 1 duplicate skipped</div>
                  <div>
                    <span className="p">›</span> /apply
                  </div>
                  <div style={{ color: "#fde68a" }}>
                    ⏸ Paused at L0 — review the draft, then click Submit yourself
                  </div>
                </div>
              </div>
              <div className={styles.note}>
                <span className={styles.noteLabel}>Note</span>
                <span className={styles.noteBody}>
                  The default consent level is L0 — nothing is ever submitted without you. Raise it
                  later in <span style={{ fontFamily: "var(--font-mono)", fontSize: 12.5 }}>Settings → Autopilot</span>.
                </span>
              </div>
            </section>

            <div className={styles.nextGrid}>
              <a href="#" className={styles.nextCard}>
                <span className={styles.nextLabel}>Next</span>
                <span className={styles.nextLink}>Connect to Claude →</span>
              </a>
              <a href="#" className={styles.nextCard}>
                <span className={styles.nextLabel}>Concepts</span>
                <span className={styles.nextLink}>Consent levels (L0–L2) →</span>
              </a>
            </div>
          </main>

          {/* on this page */}
          <aside className={styles.toc} aria-label="On this page">
            <span className={styles.tocLabel}>On this page</span>
            <a href="#docs-install" className={`${styles.tocLink} ${styles.tocLinkActive}`}>
              1. Install
            </a>
            <a href="#docs-connect" className={styles.tocLink}>
              2. Connect your AI
            </a>
            <a href="#docs-profile" className={styles.tocLink}>
              3. Build your profile
            </a>
            <a href="#docs-hunt" className={styles.tocLink}>
              4. Hunt and apply
            </a>
            <div className={styles.tocFoot}>
              <a href="https://github.com/mcpforwork">Edit on GitHub</a>
              <a href="https://github.com/mcpforwork/issues">Report an issue</a>
            </div>
          </aside>
        </div>
      </div>
    </div>
  );
}
