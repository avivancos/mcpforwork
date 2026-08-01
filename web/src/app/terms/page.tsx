import { LegalShell } from "@/components/legal/LegalShell";
import styles from "@/components/legal/legal.module.css";

export const metadata = {
  title: "Terms of Service — mcpfor.work",
  description: "The terms for using mcpfor.work: what it is, your responsibilities, the flat $5/mo plan after a 7-day trial, and the open-source self-host option.",
};

export default function TermsPage() {
  return (
    <LegalShell
      title="Terms of Service"
      updated="11 July 2026"
      lead="These terms cover the hosted mcpfor.work service. The software is open source (Apache-2.0) and free to self-host under its licence."
    >
      <section className={styles.section}>
        <h2 className={styles.h2}>The short version</h2>
        <ul className={styles.list}>
          <li>mcpfor.work is a tool that connects your own AI to job portals. You stay in control.</li>
          <li>You&rsquo;re responsible for the applications you submit and for following each job site&rsquo;s own rules.</li>
          <li>7-day free trial, then a single flat plan at $5/month. Cancel any time.</li>
          <li>We don&rsquo;t guarantee interviews or jobs — we help you apply well and honestly.</li>
        </ul>
      </section>

      <section className={styles.section}>
        <h2 className={styles.h2}>What the service is</h2>
        <p className={styles.p}>
          mcpfor.work connects the Claude or ChatGPT you already pay for to real job portals. The
          intelligence runs in your own AI client, and any browser automation runs in your own
          browser session. We provide the connector, storage, playbooks, and record — we never
          operate an AI on your behalf or act as you on a server.
        </p>
      </section>

      <section className={styles.section}>
        <h2 className={styles.h2}>Your responsibilities</h2>
        <ul className={styles.list}>
          <li>You are responsible for every application you submit and the accuracy of what it claims.</li>
          <li>You must comply with the terms of the job sites you use, and applicable law.</li>
          <li>You solve any captchas yourself — the product never bypasses them.</li>
          <li>Keep your email account secure; it&rsquo;s how you sign in.</li>
        </ul>
      </section>

      <section className={styles.section}>
        <h2 className={styles.h2}>Autopilot &amp; consent</h2>
        <p className={styles.p}>
          By default nothing is submitted without you (consent level L0). Higher levels (L1/L2) only
          run under a policy you explicitly set — minimum score, daily cap, allowlisted sites — and
          only in your own browser, interruptible at any time. You remain responsible for
          applications submitted under any level.
        </p>
      </section>

      <section className={styles.section}>
        <h2 className={styles.h2}>Trial, subscription &amp; billing</h2>
        <ul className={styles.list}>
          <li>The hosted service starts with a 7-day free trial.</li>
          <li>After the trial it&rsquo;s a single flat plan at $5/month — no tiers, no seats.</li>
          <li>Payments are processed by Stripe; you can cancel any time and keep access until the end of the paid period.</li>
          <li>We&rsquo;ll give reasonable notice before any price change.</li>
        </ul>
      </section>

      <section className={styles.section}>
        <h2 className={styles.h2}>Open source &amp; self-host</h2>
        <p className={styles.p}>
          The software is licensed under Apache-2.0. You may self-host the full product for free; the
          hosted plan buys convenience (managed connector, sync, backups, live pack updates), not
          extra capability.
        </p>
      </section>

      <section className={styles.section}>
        <h2 className={styles.h2}>Acceptable use</h2>
        <ul className={styles.list}>
          <li>No unlawful use, harassment, or misrepresentation.</li>
          <li>No abusing job sites, circumventing their protections, or bypassing captchas.</li>
          <li>No reselling or redistributing the hosted service as your own.</li>
        </ul>
      </section>

      <section className={styles.section}>
        <h2 className={styles.h2}>No employment guarantee</h2>
        <p className={styles.p}>
          We help you find and apply to roles; we don&rsquo;t promise interviews, offers, or
          outcomes. The honesty tools (like the facts inventory) exist so your materials stay
          truthful — but the responsibility for what you submit is yours.
        </p>
      </section>

      <section className={styles.section}>
        <h2 className={styles.h2}>Disclaimers &amp; liability</h2>
        <p className={styles.p}>
          The service is provided &ldquo;as is,&rdquo; without warranties to the extent permitted by
          law. To the extent permitted by law, our liability is limited — the final version reviewed
          by counsel will state the exact terms.
        </p>
      </section>

      <section className={styles.section}>
        <h2 className={styles.h2}>Termination, changes &amp; contact</h2>
        <p className={styles.p}>
          You can close your account any time. We may suspend accounts that breach these terms.
          We&rsquo;ll post material changes here and, where appropriate, notify you. Questions:{" "}
          <a href="mailto:hello@mcpfor.work" style={{ color: "var(--accent)", fontWeight: 500 }}>hello@mcpfor.work</a>.
        </p>
      </section>
    </LegalShell>
  );
}
