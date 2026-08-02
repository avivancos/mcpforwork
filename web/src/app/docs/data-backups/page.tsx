import { DocsShell } from "@/components/docs/DocsShell";
import styles from "../docs.module.css";

export const metadata = { title: "Data & backups — mcpfor.work docs" };

export default function DataBackupsPage() {
  return (
    <DocsShell
      slug="/docs/data-backups"
      title="Data & backups"
      lead="You own your data — literally: everything lives in one SQLite file on your machine. Export and delete are product features, not support tickets."
      toc={[
        { id: "where", label: "Where the data lives" },
        { id: "export", label: "Export" },
        { id: "delete", label: "Delete" },
        { id: "backups", label: "Backups" },
      ]}
    >
      <section className={styles.section} id="where">
        <h2 className={styles.h2}>Where the data lives</h2>
        <p className={styles.p}>
          A bare install stores everything in{" "}
          <code className={styles.inlineCode}>~/.mcpforwork/mcpforwork.db</code> (override with{" "}
          <code className={styles.inlineCode}>MCPFORWORK_DATA_DIR</code> or a full{" "}
          <code className={styles.inlineCode}>MCPFORWORK_DB_URL</code>). The compose stack mounts
          the same directory as a named volume at <code className={styles.inlineCode}>/data</code>{" "}
          in the containers. Profiles, matches, applications, generated assets, sessions, and the
          audit trail are all in that one file (the derived{" "}
          <code className={styles.inlineCode}>assets/</code> directory alongside it is
          re-materialized from database content, so the file alone is a complete backup).
        </p>
      </section>

      <section className={styles.section} id="export">
        <h2 className={styles.h2}>Export</h2>
        <p className={styles.p}>
          Three equivalent paths, same payload — profile, matches, applications, assets, audit
          trail, as JSON: the dashboard&rsquo;s account → data page (downloads a file),{" "}
          <code className={styles.inlineCode}>POST /v1/account/export</code> on the API, or the{" "}
          <code className={styles.inlineCode}>export_my_data</code> MCP tool from your agent client.
        </p>
      </section>

      <section className={styles.section} id="delete">
        <h2 className={styles.h2}>Delete</h2>
        <p className={styles.p}>
          Account → data → delete erases every personal row — sessions first, so the browser is
          signed out immediately. Self-host deletion is instant: there is no confirmation email
          because there is no mailer. The same guarantee is callable as{" "}
          <code className={styles.inlineCode}>delete_my_data</code> over MCP or{" "}
          <code className={styles.inlineCode}>POST /v1/account/delete</code> over HTTP.
        </p>
      </section>

      <section className={styles.section} id="backups">
        <h2 className={styles.h2}>Backups</h2>
        <p className={styles.p}>
          Back up the data directory — copying the SQLite file while the stack is stopped is a
          complete backup. For a live snapshot use{" "}
          <code className={styles.inlineCode}>sqlite3 mcpforwork.db &quot;.backup backup.db&quot;</code>.
          With compose, back up the named volume instead
          (<code className={styles.inlineCode}>docker run --rm -v mcpforwork_data:/data -v $PWD:/backup alpine tar czf /backup/data.tgz /data</code>).
          Restoring is putting the file back and starting the stack.
        </p>
      </section>
    </DocsShell>
  );
}
