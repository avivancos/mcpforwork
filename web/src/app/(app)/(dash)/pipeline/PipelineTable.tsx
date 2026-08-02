"use client";

import Link from "next/link";
import { useState, useTransition } from "react";
import { StageChip } from "@/components/StageChip";
import { approveMatch, discardMatch, recordOutcome, restoreMatch } from "@/lib/actions";
import { CONSENT_LABELS, type Outcome, type PipelineItem } from "@/lib/api/types";
import { timeAgo } from "@/lib/time";
import styles from "./pipeline.module.css";

type Filter = "all" | "matches" | "applications" | "outcomes";

const FILTERS: { key: Filter; label: string }[] = [
  { key: "all", label: "All" },
  { key: "matches", label: "Matches" },
  { key: "applications", label: "Applications" },
  { key: "outcomes", label: "Outcomes" },
];

const GROUP: Record<Filter, (i: PipelineItem) => boolean> = {
  all: () => true,
  matches: (i) => i.stage === "new_match" || i.stage === "discarded",
  applications: (i) =>
    i.stage === "filling" || i.stage === "awaiting_you" || i.stage === "submitted" || i.stage === "verified",
  outcomes: (i) =>
    i.stage === "interview" || i.stage === "offer" || i.stage === "rejected" || i.stage === "no_response",
};

const OUTCOMES: { key: Outcome; label: string }[] = [
  { key: "interview", label: "Interview scheduled" },
  { key: "offer", label: "Offer received" },
  { key: "rejected", label: "Rejected" },
  { key: "no_response", label: "No response" },
];

function OutcomeMenu({ id }: { id: string }) {
  const [, start] = useTransition();
  return (
    <details className={styles.outcome}>
      <summary className={styles.mutedAction}>Outcome…</summary>
      <div className={styles.outcomeMenu}>
        {OUTCOMES.map((o) => (
          <button
            key={o.key}
            type="button"
            className={styles.outcomeItem}
            onClick={(e) => {
              (e.currentTarget.closest("details") as HTMLDetailsElement).open = false;
              start(() => recordOutcome(id, o.key));
            }}
          >
            {o.label}
          </button>
        ))}
      </div>
    </details>
  );
}

function RowAction({ item }: { item: PipelineItem }) {
  const [pending, start] = useTransition();

  switch (item.stage) {
    case "new_match":
      return (
        <>
          <button
            type="button"
            className={`btn--approve ${styles.btnCompact}`}
            disabled={pending}
            onClick={() => start(() => approveMatch(item.id))}
          >
            Approve
          </button>
          <button
            type="button"
            className={`btn--ghost ${styles.btnCompact}`}
            disabled={pending}
            onClick={() => start(() => discardMatch(item.id))}
          >
            Discard
          </button>
        </>
      );
    case "awaiting_you":
      return (
        <Link href={`/matches/${item.id}`} className={styles.openLink}>
          Open →
        </Link>
      );
    case "discarded":
      return (
        <button
          type="button"
          className={styles.mutedAction}
          disabled={pending}
          onClick={() => start(() => restoreMatch(item.id))}
        >
          Restore
        </button>
      );
    case "submitted":
    case "verified":
    case "interview":
      return <OutcomeMenu id={item.id} />;
    default:
      return (
        <Link href={`/matches/${item.id}`} className={styles.mutedAction}>
          Open →
        </Link>
      );
  }
}

export function PipelineTable({ items }: { items: PipelineItem[] }) {
  const [filter, setFilter] = useState<Filter>("all");
  const visible = items.filter(GROUP[filter]);

  return (
    <div className={styles.section}>
      <div className={styles.tableHead}>
        <span className={styles.sectionHead}>Everything · {visible.length}</span>
        <div className={styles.pills} role="tablist" aria-label="Filter pipeline">
          {FILTERS.map((f) => (
            <button
              key={f.key}
              type="button"
              role="tab"
              aria-selected={filter === f.key}
              className={`${styles.pill} ${filter === f.key ? styles.pillActive : ""}`}
              onClick={() => setFilter(f.key)}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      <div className={styles.table}>
        <div className={styles.headerRow} aria-hidden>
          <span>Fit</span>
          <span>Role</span>
          <span>Stage</span>
          <span>Consent</span>
          <span>Updated</span>
          <span style={{ textAlign: "right" }}>Action</span>
        </div>

        {visible.length === 0 ? (
          <div className={styles.empty}>
            No matches yet — run <span className="code-chip">/hunt</span> in your client. Results land here.
          </div>
        ) : (
          visible.map((item) => (
            <div
              key={item.id}
              className={`${styles.row} ${item.stage === "new_match" ? styles.rowNew : ""} ${
                item.stage === "discarded" ? styles.rowFaded : ""
              }`}
            >
              <span className={`${styles.fit} ${item.fit >= 90 ? styles.fitHigh : ""}`}>{item.fit}</span>
              <div style={{ minWidth: 0 }}>
                <div className={styles.roleName}>{item.role}</div>
                <div className={styles.roleWhere}>
                  {item.company} · {item.city}
                </div>
              </div>
              <span style={{ justifySelf: "start" }}>
                <StageChip stage={item.stage} />
              </span>
              <span className={styles.consent}>
                {item.consent ? (
                  <>
                    {CONSENT_LABELS[item.consent]} ·{" "}
                    <Link href={`/matches/${item.id}#audit`} className={styles.auditLink}>
                      audit
                    </Link>
                  </>
                ) : (
                  "—"
                )}
              </span>
              <span className={styles.updated}>{timeAgo(item.updated)}</span>
              <div className={styles.action}>
                <RowAction item={item} />
              </div>
            </div>
          ))
        )}
      </div>

      <div className={styles.hint}>
        Want more matches? Run <span className="code-chip">/hunt</span> in your client — results land here.
      </div>
    </div>
  );
}
