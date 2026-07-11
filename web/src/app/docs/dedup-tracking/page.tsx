import { DocsShell } from "@/components/docs/DocsShell";
import styles from "../docs.module.css";

export const metadata = { title: "Dedup & tracking — mcpfor.work docs" };

export default function DedupTrackingPage() {
  return (
    <DocsShell
      slug="/docs/dedup-tracking"
      title="Dedup & tracking"
      lead="The same job is posted to five boards and reposted every two weeks. mcpfor.work canonicalizes and remembers, so you never apply twice by accident."
      toc={[
        { id: "canonical", label: "Canonical URLs" },
        { id: "seen", label: "The check_seen gate" },
        { id: "tracked", label: "Everything tracked" },
      ]}
    >
      <section className={styles.section} id="canonical">
        <h2 className={styles.h2}>Canonical URLs</h2>
        <p className={styles.p}>
          Every posting is reduced to a canonical form — stripping tracking parameters and aggregator
          wrappers — and hashed. Two links that lead to the same role collapse to one, whether they
          came from the company site, an aggregator, or a recruiter&rsquo;s repost.
        </p>
      </section>

      <section className={styles.section} id="seen">
        <h2 className={styles.h2}>The check_seen gate</h2>
        <p className={styles.p}>
          Before any application — supervised or autopilot — a dedup gate runs against everything
          you&rsquo;ve tracked. A job you already applied to is blocked; a reposting you saw last
          week is flagged, not re-surfaced as new.
        </p>
        <div className="term">
          <div className="term__bar">
            <span>Claude</span>
          </div>
          <div className="term__body">
            <div>
              <span className="p">›</span> /hunt icu nurse dublin
            </div>
            <div className="a">12 found · 3 new · 1 duplicate skipped — seen 12 days ago on IrishJobs</div>
          </div>
        </div>
      </section>

      <section className={styles.section} id="tracked">
        <h2 className={styles.h2}>Everything tracked</h2>
        <p className={styles.p}>
          Applications you make elsewhere can be recorded too, so the dedup gate and your pipeline
          stay complete. Every application, its consent level, and its outcome live in your history —
          yours to export or delete any time.
        </p>
      </section>
    </DocsShell>
  );
}
