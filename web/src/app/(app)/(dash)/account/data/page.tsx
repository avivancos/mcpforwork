import { api, usingFixtures } from "@/lib/api";
import { timeAgo } from "@/lib/time";
import dashStyles from "../../dash.module.css";
import { TopBar } from "../../TopBar";
import { AccountNav } from "../AccountNav";
import styles from "../account.module.css";
import { DataActions, DeleteAccount } from "./DataActions";

export const metadata = { title: "Data & privacy — mcpfor.work" };

export default async function DataPage() {
  const audit = await api.listAudit();

  return (
    <>
      <TopBar title="Account" />
      <div className={dashStyles.content}>
        <div className={styles.col}>
          <AccountNav />

          <div className={styles.card}>
            <span className={styles.cardTitle}>Your data leaves when you do</span>
            <span className={styles.note}>
              Export everything — profile, matches, applications, audit trail — as JSON. Salary
              floor stays private in exports marked for sharing.
            </span>
            <DataActions preview={usingFixtures} />
          </div>

          <div className={styles.card}>
            <span className={styles.cardTitle}>Audit log</span>
            <div>
              {audit.length === 0 ? (
                <div className={styles.auditRow} style={{ color: "var(--ink-4)" }}>
                  No activity yet — consent decisions, submits, and profile changes land here.
                </div>
              ) : (
                audit.map((e, i) => (
                  <div key={i} className={styles.auditRow}>
                    <span className={styles.auditAt}>{timeAgo(e.at)}</span>
                    <span>{e.event}</span>
                  </div>
                ))
              )}
            </div>
            <span className={styles.note}>
              Every consent decision, submit, and profile change is recorded here.
            </span>
          </div>

          <div className={`${styles.card} ${styles.dangerCard}`}>
            <span className={styles.dangerTitle}>Delete account</span>
            <span className={styles.note}>
              Removes your account and all data — profile, matches, applications, audit trail.
              This cannot be undone. Self-host data on your machine is unaffected.
            </span>
            <DeleteAccount preview={usingFixtures} />
          </div>
        </div>
      </div>
    </>
  );
}
