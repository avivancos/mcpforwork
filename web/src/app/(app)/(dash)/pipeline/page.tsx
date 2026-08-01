import Link from "next/link";
import { api } from "@/lib/api";
import dashStyles from "../dash.module.css";
import { TopBar } from "../TopBar";
import { PipelineTable } from "./PipelineTable";
import styles from "./pipeline.module.css";

export const metadata = { title: "Pipeline — mcpfor.work" };

export default async function PipelinePage() {
  const [stats, items] = await Promise.all([api.getPipelineStats(), api.listPipeline()]);
  const needsYou = items.filter((i) => i.stage === "awaiting_you");

  return (
    <>
      <TopBar title="Pipeline" />
      <div className={dashStyles.content}>
        {/* insight strip */}
        <div className={styles.stats}>
          <div className={styles.tile}>
            <span className={styles.tileLabel}>
              <span className={styles.tileLabelLong}>New matches</span>
              <span className={styles.tileLabelShort}>new</span>
            </span>
            <span className={styles.tileValue}>{stats.newMatches.count}</span>
            <span className={styles.tileSub}>of {stats.newMatches.foundThisWeek} found this week</span>
          </div>
          <div className={`${styles.tile} ${styles.tileWarn}`}>
            <span className={styles.tileLabel}>Needs you</span>
            <span className={styles.tileValue}>{stats.needsYou.count}</span>
            <span className={styles.tileSub}>paused at Submit</span>
          </div>
          <div className={styles.tile}>
            <span className={styles.tileLabel}>Submitted</span>
            <span className={styles.tileValue}>{stats.submitted.count}</span>
            <span className={styles.tileSub}>{stats.submitted.verified} verified · all supervised</span>
          </div>
          <div className={`${styles.tile} ${styles.tileResponses}`}>
            <span className={styles.tileLabel}>Responses</span>
            <span className={styles.tileValue}>
              {stats.responses.count}
              <span className={styles.tileValueDim}>/{stats.responses.of}</span>
            </span>
            <span className={styles.tileSub}>{stats.responses.interviews} interview scheduled</span>
          </div>
        </div>

        {/* needs you */}
        {needsYou.length > 0 && (
          <div className={styles.section}>
            <span className={`${styles.sectionHead} ${styles.sectionHeadWarn}`}>
              Needs you · {needsYou.length}
            </span>
            <div className={styles.needsCard}>
              {needsYou.map((item) => (
                <div key={item.id} className={styles.needsRow}>
                  <div>
                    <div className={styles.needsTitle}>
                      {item.role} — {item.company}
                    </div>
                    <div className={styles.needsContext}>{item.needsYou}</div>
                  </div>
                  <span className={styles.chipSlot}>
                    <span className="chip chip--amber">awaiting you</span>
                  </span>
                  <Link href={`/matches/${item.id}`} className={styles.reviewBtn}>
                    Review in Claude →
                  </Link>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* everything */}
        <PipelineTable items={items} />
      </div>
    </>
  );
}
