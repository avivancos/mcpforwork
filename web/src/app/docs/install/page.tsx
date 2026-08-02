import { DocsShell } from "@/components/docs/DocsShell";
import styles from "../docs.module.css";

export const metadata = { title: "Install & run — mcpfor.work docs" };

export default function InstallPage() {
  return (
    <DocsShell
      slug="/docs/install"
      title="Install & run"
      lead="Two ways to run self-host: a bare uvx install for just the MCP server in your agent client, or docker compose for the full stack — MCP over HTTP, the API, and the dashboard."
      toc={[
        { id: "uvx", label: "uvx (MCP only)" },
        { id: "compose", label: "docker compose (full stack)" },
        { id: "connect", label: "Connect your client" },
      ]}
    >
      <section className={styles.section} id="uvx">
        <h2 className={styles.h2}>uvx (MCP only)</h2>
        <p className={styles.p}>
          No install step — <code className={styles.inlineCode}>uvx</code> runs the server straight
          from the package. Initialize the local database once:
        </p>
        <div className="term">
          <div className="term__bar">
            <span>shell</span>
          </div>
          <div className="term__body">
            <div>
              <span className="p">$</span> uvx --from mcpforwork mcpforwork init
            </div>
            <div className="a">Initialized sqlite:///~/.mcpforwork/mcpforwork.db</div>
          </div>
        </div>
        <p className={styles.p}>
          Your agent client launches the server over stdio with{" "}
          <code className={styles.inlineCode}>uvx --from mcpforwork mcpforwork-mcp</code> — the
          connect command below generates the exact block to paste.
        </p>
      </section>

      <section className={styles.section} id="compose">
        <h2 className={styles.h2}>docker compose (full stack)</h2>
        <p className={styles.p}>
          The repo ships a compose file with three services:{" "}
          <code className={styles.inlineCode}>mcp</code> (streamable-HTTP on :8500),{" "}
          <code className={styles.inlineCode}>api</code> (the REST API on :8000), and{" "}
          <code className={styles.inlineCode}>web</code> (the dashboard). One image builds both
          Python entrypoints.
        </p>
        <div className="term">
          <div className="term__bar">
            <span>shell</span>
          </div>
          <div className="term__body">
            <div>
              <span className="p">$</span> cp .env.example .env && $EDITOR .env
            </div>
            <div>
              <span className="p">$</span> docker compose up -d --build
            </div>
            <div className="a">mcp :8500 · api :8000 · web :2200</div>
          </div>
        </div>
        <p className={styles.p}>
          <code className={styles.inlineCode}>MCPFORWORK_SESSION_SECRET</code> is required — the API
          refuses to boot without it. Sign in at the dashboard with your email; the console mailer
          prints the magic link to the API logs (<code className={styles.inlineCode}>docker compose logs api</code>).
        </p>
      </section>

      <section className={styles.section} id="connect">
        <h2 className={styles.h2}>Connect your client</h2>
        <p className={styles.p}>
          One command prints the exact config for Claude Code, Claude Desktop, Cursor, Codex, or
          OpenCode — in either run mode:
        </p>
        <div className="term">
          <div className="term__bar">
            <span>shell</span>
          </div>
          <div className="term__body">
            <div>
              <span className="p">$</span> mcpforwork connect --client cursor
            </div>
            <div>
              <span className="p">$</span> mcpforwork connect --mode compose
            </div>
          </div>
        </div>
        <p className={styles.p}>
          Then run <code className={styles.inlineCode}>/setup</code> in your client to build your
          profile. Compose mode is single-tenant: the networked MCP endpoint shares the one local
          user (ADR 0006).
        </p>
      </section>
    </DocsShell>
  );
}
