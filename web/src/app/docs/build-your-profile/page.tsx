import { DocsShell } from "@/components/docs/DocsShell";
import styles from "../docs.module.css";

export const metadata = { title: "Build your profile — mcpfor.work docs" };

export default function BuildYourProfilePage() {
  return (
    <DocsShell
      slug="/docs/build-your-profile"
      title="Build your profile"
      lead="Your profile is what makes matches accurate and drafts honest. The required tier takes under three minutes; depth is progressive — asked only when a posting actually needs it."
      toc={[
        { id: "tier1", label: "Tier 1 — the essentials" },
        { id: "tier2", label: "Tier 2 — depth" },
        { id: "private", label: "What stays private" },
      ]}
    >
      <section className={styles.section} id="tier1">
        <h2 className={styles.h2}>Tier 1 — the essentials</h2>
        <p className={styles.p}>
          A handful of fields turn into hard filters every match is scored against: target roles and
          sector, location and work authorization, employment type and work mode, languages, and a
          private salary floor. Paste your CV or share a LinkedIn URL and your client extracts the
          rest.
        </p>
        <div className={styles.chatSample}>
          <span className={styles.chatUser}>/profile — here&rsquo;s my CV (attached)</span>
          <span className={styles.chatBot}>
            Extracted 18 facts. Two quick ones: which cities, and do you need visa sponsorship?
          </span>
        </div>
      </section>

      <section className={styles.section} id="tier2">
        <h2 className={styles.h2}>Tier 2 — depth (optional)</h2>
        <p className={styles.p}>
          Each unlock measurably improves output. The highest-leverage input is your{" "}
          <strong style={{ fontWeight: 600 }}>achievements bank</strong> — quantified wins with
          metric, context, and role — which turns generic bullets into specific ones. A short
          writing sample builds a style profile so drafts sound like you, not like AI. Deal-breakers
          and a career narrative sharpen fit scoring.
        </p>
        <p className={styles.p}>
          You add these in your client, contextually. When a posting asks about notice period, your
          AI offers to save it — so the question is never asked twice.
        </p>
      </section>

      <section className={styles.section} id="private">
        <h2 className={styles.h2}>What stays private</h2>
        <div className={styles.note}>
          <span className={styles.noteLabel}>Private</span>
          <span className={styles.noteBody}>
            Your salary floor is a filter only — never disclosed in any application without your
            explicit consent. Optional EEO/demographic fields are encrypted at rest, never used in
            scoring, and only ever pre-fill voluntary sections. Everything is yours to export or
            delete at any time.
          </span>
        </div>
      </section>
    </DocsShell>
  );
}
