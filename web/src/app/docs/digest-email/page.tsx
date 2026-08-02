import { DocsShell } from "@/components/docs/DocsShell";
import styles from "../docs.module.css";

export const metadata = { title: "Digest email — mcpfor.work docs" };

export default function DigestEmailPage() {
  return (
    <DocsShell
      slug="/docs/digest-email"
      title="Digest email"
      lead="A periodic email summarizing what your pipeline did — new matches, applications sent, outcomes — is part of the product plan. Here is the honest state of it in self-host."
      toc={[
        { id: "planned", label: "What the digest is" },
        { id: "selfhost", label: "Self-host today" },
      ]}
    >
      <section className={styles.section} id="planned">
        <h2 className={styles.h2}>What the digest is</h2>
        <p className={styles.p}>
          The digest is the &ldquo;wake up to progress&rdquo; loop: a periodic email with the new
          matches since last time, where each application stands, and anything waiting on your
          approval. It is what makes autopilot feel supervised even when you are not watching the
          dashboard.
        </p>
      </section>

      <section className={styles.section} id="selfhost">
        <h2 className={styles.h2}>Self-host today</h2>
        <p className={styles.p}>
          Self-host ships no mailer and no scheduler — the only email the system produces is the
          magic sign-in link, and the console mailer prints it to the API logs instead of sending
          it. The digest is hosted-track scope: it needs a real mail provider and a scheduler,
          both of which live behind ports so a hosted deployment can supply them.
        </p>
        <p className={styles.p}>
          In the meantime the dashboard pipeline and{" "}
          <code className={styles.inlineCode}>pipeline_stats</code> answer the same question on
          demand — and every state change is in your audit log, exportable any time.
        </p>
      </section>
    </DocsShell>
  );
}
