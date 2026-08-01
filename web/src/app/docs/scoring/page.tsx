import { DocsShell } from "@/components/docs/DocsShell";
import styles from "../docs.module.css";

export const metadata = { title: "Scoring & constraints — mcpfor.work docs" };

export default function ScoringPage() {
  return (
    <DocsShell
      slug="/docs/scoring"
      title="Scoring & constraints"
      lead="Every match is scored against the constraints you set once — not a hardcoded idea of a 'good job'. Hard filters gate; fit ranks what's left."
      toc={[
        { id: "constraints", label: "Hard constraints" },
        { id: "fit", label: "Fit score" },
        { id: "sector", label: "Sector-driven, not hardcoded" },
      ]}
    >
      <section className={styles.section} id="constraints">
        <h2 className={styles.h2}>Hard constraints</h2>
        <p className={styles.p}>
          The deal-breakers from your profile are applied before you ever see a match: work
          authorization, salary floor, languages, work mode, and your explicit veto filters. A role
          that fails a hard constraint is filtered out — you don&rsquo;t waste attention on it.
        </p>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          {["visa ✓", "€52k ✓", "EN C1 ✓", "relocation ✓"].map((c) => (
            <span key={c} className="chip chip--green" style={{ borderRadius: 5 }}>
              {c}
            </span>
          ))}
        </div>
      </section>

      <section className={styles.section} id="fit">
        <h2 className={styles.h2}>Fit score</h2>
        <p className={styles.p}>
          What survives the filters is ranked by a fit score — how well the posting matches your
          target roles, seniority, and the strengths in your profile. It&rsquo;s a guide for where to
          spend effort, and (optionally) the threshold autopilot respects. High scores surface first;
          nothing is hidden.
        </p>
      </section>

      <section className={styles.section} id="sector">
        <h2 className={styles.h2}>Sector-driven, not hardcoded</h2>
        <div className={styles.note}>
          <span className={styles.noteLabel}>Any sector</span>
          <span className={styles.noteBody}>
            Scoring is driven by the sector pack for your field — a nurse, a logistics coordinator,
            and a frontend developer are each evaluated on what matters in their market, not a single
            baked-in persona.
          </span>
        </div>
      </section>
    </DocsShell>
  );
}
