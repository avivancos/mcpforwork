import { DocsShell } from "@/components/docs/DocsShell";
import styles from "../docs.module.css";

export const metadata = { title: "Configuration — mcpfor.work docs" };

const CORE: { name: string; def: string; what: string }[] = [
  { name: "MCPFORWORK_DATA_DIR", def: "~/.mcpforwork", what: "where the SQLite database and uploaded files live" },
  { name: "MCPFORWORK_DB_URL", def: "sqlite:///<data dir>/mcpforwork.db", what: "database URL; set a postgres:// URL for the Postgres adapter" },
  { name: "MCPFORWORK_USER_EMAIL", def: "local@self-host", what: "the single tenant's identity — MCP server and dashboard resolve to the same user by email" },
  { name: "MCPFORWORK_USER_ID", def: "unset", what: "optional numeric pin for the local MCP process; prefer the email" },
  { name: "MCPFORWORK_DB_RUN_MIGRATIONS", def: "1", what: "set 0 to skip auto-migrations on connect (you run them yourself)" },
  { name: "MCPFORWORK_TRANSPORT", def: "stdio", what: "MCP transport; streamable-http for the compose service" },
];

const API: { name: string; def: string; what: string }[] = [
  { name: "MCPFORWORK_SESSION_SECRET", def: "required", what: "signs session cookies — the API refuses to boot without it" },
  { name: "MCPFORWORK_COOKIE_SECURE", def: "1", what: "set 0 for plain-http local development" },
  { name: "MCPFORWORK_ALLOWED_HOSTS", def: "localhost, 127.0.0.1", what: "Host-header allowlist (TrustedHost)" },
  { name: "MCPFORWORK_PUBLIC_BASE_URL", def: "unset (request origin)", what: "origin used in magic links — set it in any hosted deploy; never trusts the request's Host header" },
  { name: "MCPFORWORK_POST_LOGIN_REDIRECT", def: "unset", what: "where the browser lands after redeeming a magic link (e.g. the dashboard)" },
  { name: "MCPFORWORK_API_HOST", def: "127.0.0.1", what: "bind address" },
  { name: "MCPFORWORK_API_PORT", def: "8080", what: "bind port" },
];

const WEB: { name: string; def: string; what: string }[] = [
  { name: "MCPFORWORK_API_URL", def: "unset (demo fixtures)", what: "the API origin the dashboard talks to — unset runs the demo dataset, not your data" },
  { name: "MCPFORWORK_FIXTURES", def: "unset", what: "set 1 to run the dashboard on the demo dataset instead of the API" },
];

function VarTable({ rows }: { rows: { name: string; def: string; what: string }[] }) {
  return (
    <p className={styles.p}>
      {rows.map((v) => (
        <span key={v.name} style={{ display: "block", marginBottom: 8 }}>
          <code className={styles.inlineCode}>{v.name}</code>{" "}
          <span style={{ opacity: 0.6 }}>(default: {v.def})</span> — {v.what}
        </span>
      ))}
    </p>
  );
}

export default function ConfigurationPage() {
  return (
    <DocsShell
      slug="/docs/configuration"
      title="Configuration"
      lead="Everything is environment variables — no config file format to learn. The compose stack reads them from .env; a bare uvx install inherits your shell. Copy .env.example as the starting point."
      toc={[
        { id: "core", label: "Core (MCP + CLI)" },
        { id: "api", label: "API" },
        { id: "web", label: "Dashboard" },
      ]}
    >
      <section className={styles.section} id="core">
        <h2 className={styles.h2}>Core (MCP server + CLI)</h2>
        <VarTable rows={CORE} />
      </section>

      <section className={styles.section} id="api">
        <h2 className={styles.h2}>API</h2>
        <VarTable rows={API} />
        <div className={styles.note}>
          <span className={styles.noteLabel}>Single-tenant</span>
          <span className={styles.noteBody}>
            Self-host is one tenant: the MCP server and the dashboard resolve to the same user via{" "}
            <code className={styles.inlineCode}>MCPFORWORK_USER_EMAIL</code>. Multi-tenant HTTP auth
            is hosted-track scope (ADR 0006).
          </span>
        </div>
      </section>

      <section className={styles.section} id="web">
        <h2 className={styles.h2}>Dashboard</h2>
        <VarTable rows={WEB} />
      </section>
    </DocsShell>
  );
}
