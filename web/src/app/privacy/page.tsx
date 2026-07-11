import { LegalShell } from "@/components/legal/LegalShell";
import styles from "@/components/legal/legal.module.css";

export const metadata = {
  title: "Privacy Policy — mcpfor.work",
  description: "How mcpfor.work handles your data: magic-link auth, zero server-side LLM, private salary floor, and export or delete any time.",
};

export default function PrivacyPage() {
  return (
    <LegalShell
      title="Privacy Policy"
      updated="11 July 2026"
      lead="This policy covers the hosted mcpfor.work service. If you self-host, your data lives on your own machine and this policy does not apply — nothing leaves your computer."
    >
      <section className={styles.section}>
        <h2 className={styles.h2}>The short version</h2>
        <ul className={styles.list}>
          <li>We sign you in with a magic link — there is no password to store or leak.</li>
          <li>
            We run <strong>zero server-side LLM calls</strong>. There is no model on our side, so we
            have nothing to train on your data and we never do.
          </li>
          <li>Your salary floor is private and never disclosed in any application without your consent.</li>
          <li>You can export everything as JSON, or delete your account and all data, at any time.</li>
          <li>No advertising trackers, no third-party analytics cookies.</li>
        </ul>
      </section>

      <section className={styles.section}>
        <h2 className={styles.h2}>What we collect</h2>
        <ul className={styles.list}>
          <li>
            <strong>Account:</strong> your email address, used for magic-link sign-in and (if you opt
            in) the daily digest.
          </li>
          <li>
            <strong>Profile:</strong> the details you provide to make matches accurate — target
            roles, location, work authorization, languages, a private salary floor, and any CV facts,
            achievements, or writing style you choose to add.
          </li>
          <li>
            <strong>Pipeline:</strong> the matches, applications, outcomes, and audit trail generated
            as you use the product.
          </li>
          <li>
            <strong>Optional EEO/demographic data:</strong> only if you provide it — encrypted at
            rest, never used in scoring, and only ever used to pre-fill voluntary sections you choose
            to complete.
          </li>
          <li>
            <strong>Technical:</strong> a session cookie for sign-in, and minimal operational logs to
            keep the service secure and working.
          </li>
          <li>
            <strong>Payment:</strong> handled by our payment processor (Stripe). We never see or store
            your full card details.
          </li>
        </ul>
      </section>

      <section className={styles.section}>
        <h2 className={styles.h2}>Your AI client stays yours</h2>
        <p className={styles.p}>
          The intelligence — searching, evaluating fit, drafting — runs inside your own Claude or
          ChatGPT subscription, in your own browser. We are the connector and the record; we never
          receive your AI conversations, and we make no LLM calls on our servers.
        </p>
      </section>

      <section className={styles.section}>
        <h2 className={styles.h2}>What we never do</h2>
        <ul className={styles.list}>
          <li>We don&rsquo;t sell your data, or share it for advertising.</li>
          <li>We don&rsquo;t train any model on your data (we run none).</li>
          <li>We don&rsquo;t disclose your salary floor without your explicit consent.</li>
          <li>We don&rsquo;t set advertising or cross-site tracking cookies.</li>
        </ul>
      </section>

      <section className={styles.section}>
        <h2 className={styles.h2}>Legal bases (GDPR)</h2>
        <ul className={styles.list}>
          <li>
            <strong>Contract:</strong> most processing is to provide the service you signed up for.
          </li>
          <li>
            <strong>Consent:</strong> optional EEO data and the digest email, which you can withdraw
            any time.
          </li>
          <li>
            <strong>Legitimate interest:</strong> keeping the service secure and reliable.
          </li>
        </ul>
      </section>

      <section className={styles.section}>
        <h2 className={styles.h2}>Sub-processors</h2>
        <p className={styles.p}>
          We use a small number of processors strictly to run the service: a payment processor
          (Stripe), an email delivery provider (for magic links and the digest), and cloud hosting.
          No AI vendor processes your data on our behalf. We&rsquo;ll keep an up-to-date list
          available and give notice of material changes.
        </p>
      </section>

      <section className={styles.section}>
        <h2 className={styles.h2}>Retention &amp; international transfers</h2>
        <p className={styles.p}>
          We keep your data while your account is active and delete it on request. Where data is
          processed outside your region, we rely on appropriate safeguards (such as standard
          contractual clauses) with our processors.
        </p>
      </section>

      <section className={styles.section}>
        <h2 className={styles.h2}>Your rights</h2>
        <p className={styles.p}>
          You can access, export, correct, or delete your data, restrict or object to processing, and
          withdraw consent — from your dashboard&rsquo;s{" "}
          <span className={styles.inlineCode}>Account → Data &amp; privacy</span> settings, or by
          emailing us. You may also complain to your local data-protection authority.
        </p>
      </section>

      <section className={styles.section}>
        <h2 className={styles.h2}>Children</h2>
        <p className={styles.p}>The service is not directed to anyone under 16, and we don&rsquo;t knowingly collect their data.</p>
      </section>

      <section className={styles.section}>
        <h2 className={styles.h2}>Changes &amp; contact</h2>
        <p className={styles.p}>
          We&rsquo;ll post material changes here and, where appropriate, notify you by email.
          Questions: <a href="mailto:privacy@mcpfor.work" style={{ color: "var(--accent)", fontWeight: 500 }}>privacy@mcpfor.work</a>.
        </p>
      </section>
    </LegalShell>
  );
}
