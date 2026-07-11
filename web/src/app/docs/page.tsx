import { CopyButton } from "@/components/CopyButton";
import { DocsShell } from "@/components/docs/DocsShell";
import styles from "./docs.module.css";

export const metadata = { title: "Quickstart — mcpfor.work docs" };

const CONFIG_SNIPPET = `{
  "mcpServers": {
    "mcpforwork": { "command": "uvx", "args": ["mcpforwork"] }
  }
}`;

export default function QuickstartPage() {
  return (
    <DocsShell
      slug="/docs"
      title="Quickstart"
      lead="From zero to your first supervised application in about five minutes. You'll need a Claude or ChatGPT subscription — no API key."
      toc={[
        { id: "install", label: "1. Install" },
        { id: "connect", label: "2. Connect your AI" },
        { id: "profile", label: "3. Build your profile" },
        { id: "hunt", label: "4. Hunt and apply" },
      ]}
    >
      <section className={styles.section} id="install">
        <h2 className={styles.h2}>1. Install</h2>
        <p className={styles.p}>
          Run the server locally with <span className={styles.inlineCode}>uvx</span> — no clone, no
          build step. It creates a local SQLite database on first run.
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

      <section className={styles.section} id="connect">
        <h2 className={styles.h2}>2. Connect your AI</h2>
        <p className={styles.p}>
          Add the server to Claude Desktop. Hosted users skip this — connect from claude.ai in one
          click.
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

      <section className={styles.section} id="profile">
        <h2 className={styles.h2}>3. Build your profile</h2>
        <p className={styles.p}>
          Give it your CV and answer a short interview. This builds your{" "}
          <strong style={{ fontWeight: 600 }}>facts inventory</strong> — the only source drafts may
          claim from — plus your hard constraints (visa, salary floor, language).
        </p>
        <div className={styles.chatSample}>
          <span className={styles.chatUser}>/profile — here&rsquo;s my CV (attached)</span>
          <span className={styles.chatBot}>
            Extracted 18 facts from your CV. Three quick questions: what&rsquo;s your salary floor?
            (stays private, only filters matches)
          </span>
        </div>
      </section>

      <section className={styles.section} id="hunt">
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
            The default consent level is L0 — nothing is ever submitted without you. Raise it later
            with a policy you set (see{" "}
            <a href="/docs/consent-levels" style={{ color: "var(--accent)", fontWeight: 500 }}>
              Consent levels
            </a>
            ).
          </span>
        </div>
      </section>
    </DocsShell>
  );
}
