import { LegalShell } from "@/components/legal/LegalShell";
import styles from "@/components/legal/legal.module.css";

export const metadata = {
  title: "Security — mcpfor.work",
  description: "How mcpfor.work is built to protect you: zero server-side LLM, magic-link auth, tenant isolation, encryption, and full data control.",
};

export default function SecurityPage() {
  return (
    <LegalShell
      title="Security"
      updated="11 July 2026"
      lead="Security here is mostly architectural — the safest data is the data we never handle. Here's how the product is built to protect you."
    >
      <section className={styles.section}>
        <h2 className={styles.h2}>The intelligence never touches our servers</h2>
        <p className={styles.p}>
          All the thinking runs in your own AI client and browser. We make{" "}
          <strong>zero server-side LLM calls</strong>, so your prompts and conversations never reach
          us — there&rsquo;s no model on our side to leak them, and nothing to train on your data.
        </p>
      </section>

      <section className={styles.section}>
        <h2 className={styles.h2}>Authentication</h2>
        <p className={styles.p}>
          We use magic-link sign-in — there is no password to phish, reuse, or breach. Sessions are
          scoped and can be revoked from your dashboard. Connecting your AI client uses standard
          OAuth, with a grant you can revoke at any time.
        </p>
      </section>

      <section className={styles.section}>
        <h2 className={styles.h2}>Tenant isolation</h2>
        <p className={styles.p}>
          The hosted database enforces row-level isolation so your data is only ever reachable by
          you. It&rsquo;s a structural guarantee, not a per-query convention.
        </p>
      </section>

      <section className={styles.section}>
        <h2 className={styles.h2}>Encryption &amp; sensitive fields</h2>
        <p className={styles.p}>
          Traffic is encrypted in transit (TLS). Optional demographic (EEO) data is encrypted at
          rest and never used in scoring. Your salary floor is a private field, used only to filter
          matches.
        </p>
      </section>

      <section className={styles.section}>
        <h2 className={styles.h2}>Payments</h2>
        <p className={styles.p}>
          Card payments are handled by Stripe. We never see or store your full card details.
        </p>
      </section>

      <section className={styles.section}>
        <h2 className={styles.h2}>Your control</h2>
        <ul className={styles.list}>
          <li>Export everything as JSON, or delete your account and all data, any time.</li>
          <li>Automation runs only in your own browser session — there is never a server-side robot acting as you.</li>
          <li>Prefer maximum control? Self-host: your data never leaves your machine.</li>
        </ul>
      </section>

      <section className={styles.section}>
        <h2 className={styles.h2}>Responsible disclosure</h2>
        <p className={styles.p}>
          Found a vulnerability? We welcome reports and will work with you in good faith. Email{" "}
          <a href="mailto:security@mcpfor.work" style={{ color: "var(--accent)", fontWeight: 500 }}>security@mcpfor.work</a>{" "}
          — please give us reasonable time to fix before public disclosure.
        </p>
      </section>
    </LegalShell>
  );
}
