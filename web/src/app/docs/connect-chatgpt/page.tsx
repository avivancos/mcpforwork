import { CopyButton } from "@/components/CopyButton";
import { DocsShell } from "@/components/docs/DocsShell";
import styles from "../docs.module.css";

export const metadata = { title: "Connect to ChatGPT — mcpfor.work docs" };

export default function ConnectChatGPTPage() {
  return (
    <DocsShell
      slug="/docs/connect-chatgpt"
      title="Connect to ChatGPT"
      lead="mcpfor.work is one server, both ecosystems. Connect it to ChatGPT on a paid plan, or run it from the Codex CLI — the same account, the same tools."
      toc={[
        { id: "connectors", label: "ChatGPT connectors" },
        { id: "codex", label: "Codex CLI" },
        { id: "parity", label: "Feature parity" },
      ]}
    >
      <section className={styles.section} id="connectors">
        <h2 className={styles.h2}>ChatGPT connectors</h2>
        <p className={styles.p}>
          ChatGPT supports remote MCP connectors on paid plans. Add a custom connector and paste
          your connector URL, then approve access — the same OAuth grant as Claude.
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
      </section>

      <section className={styles.section} id="codex">
        <h2 className={styles.h2}>Codex CLI</h2>
        <p className={styles.p}>
          The Codex CLI speaks MCP over stdio. Self-host runs the same server locally — no account,
          SQLite on your machine.
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
            <div className="a">✓ MCP server listening on stdio</div>
          </div>
        </div>
      </section>

      <section className={styles.section} id="parity">
        <h2 className={styles.h2}>Feature parity</h2>
        <p className={styles.p}>
          Every tool and prompt behaves identically across clients — hunting runs in your browser,
          drafts come from your{" "}
          <a href="/docs/facts-inventory" style={{ color: "var(--accent)", fontWeight: 500 }}>
            facts inventory
          </a>
          , and nothing is submitted without the{" "}
          <a href="/docs/consent-levels" style={{ color: "var(--accent)", fontWeight: 500 }}>
            consent level
          </a>{" "}
          you set. The client is the only thing that changes.
        </p>
      </section>
    </DocsShell>
  );
}
