import Link from "next/link";
import { notFound } from "next/navigation";
import { StageChip } from "@/components/StageChip";
import { api } from "@/lib/api";
import dashStyles from "../../dash.module.css";
import { TopBar } from "../../TopBar";
import { MatchActions } from "./MatchActions";
import styles from "./match.module.css";

export const metadata = { title: "Match — mcpfor.work" };

export default async function MatchPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const match = await api.getMatch(id);
  if (!match) notFound();

  return (
    <>
      <TopBar title="Match" />
      <div className={dashStyles.content}>
        <div className={styles.detailCol}>
          <Link href="/pipeline" className={styles.back}>
            ← Pipeline
          </Link>

          <div className={styles.matchCard}>
            <div className={styles.matchHead}>
              <div>
                <div className={styles.matchTitle}>
                  {match.role} — {match.company}
                </div>
                <div className={styles.matchWhere}>
                  {match.city} · {match.employmentType} ·{" "}
                  <span className={styles.packChip}>{match.pack}</span>
                </div>
              </div>
              <span className={styles.fitRing}>{match.fit}</span>
            </div>
            <div className={styles.checks}>
              {match.constraintChecks.map((c) => (
                <span key={c.label} className={`${styles.check} ${c.ok ? "" : styles.checkFail}`}>
                  {c.label} {c.ok ? "✓" : "✗"}
                </span>
              ))}
            </div>
            <div className={styles.dedup}>{match.dedup}</div>
          </div>

          <div className={styles.statusRow}>
            <StageChip stage={match.stage} size={10.5} />
            {match.consent && <span>Supervised — every submit is yours</span>}
            <span style={{ color: "var(--ink-4)" }}>Updated {match.updated}</span>
          </div>

          <MatchActions id={match.id} stage={match.stage} postingUrl={match.postingUrl} />

          {match.assets.length > 0 && (
            <div className={styles.sectionCard}>
              <div className={styles.sectionTitle}>Assets</div>
              {match.assets.map((a) => (
                <div key={a.id} className={styles.assetRow}>
                  <span className={styles.assetName}>⎘ {a.name}</span>
                  <span className={styles.assetNote}>{a.note}</span>
                </div>
              ))}
              <div className={styles.sectionFoot}>
                Drafts are written and revised in your client — this is the mirror.
              </div>
            </div>
          )}

          <div className={styles.sectionCard} id="audit">
            <div className={styles.sectionTitle}>Audit</div>
            {match.audit.length === 0 ? (
              <div className={styles.auditRow} style={{ color: "var(--ink-4)" }}>
                No application activity yet.
              </div>
            ) : (
              match.audit.map((e, i) => (
                <div key={i} className={styles.auditRow}>
                  <span className={styles.auditAt}>{e.at}</span>
                  <span>{e.event}</span>
                </div>
              ))
            )}
            <div className={styles.sectionFoot}>
              Every consent decision is recorded. Nothing is ever submitted without one.
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
