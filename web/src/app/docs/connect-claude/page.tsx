import { CopyButton } from "@/components/CopyButton";
import { DocsShell } from "@/components/docs/DocsShell";
import styles from "../docs.module.css";

export const metadata = { title: "Connect to Claude — mcpfor.work docs" };

const DESKTOP_SNIPPET = `{
  "mcpServers": {
    "mcpforwork": { "command": "uvx", "args": ["mcpforwork"] }
  }
}`;

export default function ConnectClaudePage() {
  return (
    <DocsShell
      slug="/docs/connect-claude"
      title="Connect to Claude"
      lead="Point the Claude you already pay for at your mcpfor.work server. Hosted is one click; self-host adds a few lines of config. The same account works from claude.ai, Claude Desktop, and Claude Code."
      toc={[
        { id: "hosted", label: "Hosted — one click" },
        { id: "desktop", label: "Claude Desktop" },
        { id: "code", label: "Claude Code" },
        { id: "verify", label: "Verify the connection" },
      ]}
    >
      <section className={styles.section} id="hosted">
        <h2 className={styles.h2}>Hosted — one click</h2>
        <p className={styles.p}>
          In <span className={styles.inlineCode}>claude.ai → Settings → Connectors</span>, add a
          custom connector and paste your connector URL. You approve a standard OAuth screen inside
          claude.ai — nothing to install.
        </p>
        <div className="term">
          <div className="term__bar">
            <span>connector URL</span>
            <CopyButton text="https://mcp.mcpfor.work/mcp" className="term__copy" />
          </div>
          <div className="term__body">
            <div className="a">https://mcp.mcpfor.work/mcp</div>
          </div>
        </div>
        <div className={styles.note}>
          <span className={styles.noteLabel}>Scopes</span>
          <span className={styles.noteBody}>
            The grant is read/write, scoped to your own data, and revocable any time from your
            dashboard or claude.ai. We never make server-side LLM calls — your subscription does all
            the thinking.
          </span>
        </div>
      </section>

      <section className={styles.section} id="desktop">
        <h2 className={styles.h2}>Claude Desktop (self-host)</h2>
        <p className={styles.p}>
          Self-hosting is free and identical in features. Add the stdio server to{" "}
          <span className={styles.inlineCode}>claude_desktop_config.json</span> — it runs locally on
          SQLite, no account.
        </p>
        <div className="term">
          <div className="term__bar">
            <span>claude_desktop_config.json</span>
            <CopyButton text={DESKTOP_SNIPPET} className="term__copy" />
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

      <section className={styles.section} id="code">
        <h2 className={styles.h2}>Claude Code</h2>
        <p className={styles.p}>Register the same stdio server from the terminal:</p>
        <div className="term">
          <div className="term__bar">
            <span>terminal</span>
            <CopyButton text="claude mcp add mcpforwork -- uvx mcpforwork" className="term__copy" />
          </div>
          <div className="term__body">
            <div>
              <span className="p">$</span> claude mcp add mcpforwork -- uvx mcpforwork
            </div>
            <div className="a">✓ added mcpforwork (stdio)</div>
          </div>
        </div>
      </section>

      <section className={styles.section} id="verify">
        <h2 className={styles.h2}>Verify the connection</h2>
        <p className={styles.p}>Ask Claude to say hello — the server answers with a version handshake.</p>
        <div className={styles.chatSample}>
          <span className={styles.chatUser}>are you connected to mcpfor.work?</span>
          <span className={styles.chatBot}>
            Connected — mcpfor.work v0.4.2. Next step: build your profile so I can hunt and filter
            honestly.
          </span>
        </div>
      </section>
    </DocsShell>
  );
}
