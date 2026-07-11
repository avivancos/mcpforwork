"use client";

import { useTransition } from "react";
import { approveMatch, discardMatch, restoreMatch } from "@/lib/actions";
import type { Stage } from "@/lib/api/types";
import styles from "./match.module.css";

export function MatchActions({ id, stage, postingUrl }: { id: string; stage: Stage; postingUrl: string }) {
  const [pending, start] = useTransition();

  return (
    <div className={styles.actions}>
      {stage === "new_match" && (
        <>
          <button type="button" className="btn btn--primary" disabled={pending} onClick={() => start(() => approveMatch(id))}>
            Approve
          </button>
          <button type="button" className="btn btn--secondary" disabled={pending} onClick={() => start(() => discardMatch(id))}>
            Discard
          </button>
        </>
      )}
      {stage === "awaiting_you" && (
        <a href="https://claude.ai" className="btn btn--primary">
          Review in Claude →
        </a>
      )}
      {stage === "discarded" && (
        <button type="button" className="btn btn--secondary" disabled={pending} onClick={() => start(() => restoreMatch(id))}>
          Restore
        </button>
      )}
      <a href={postingUrl} target="_blank" rel="noreferrer" className="btn btn--secondary">
        Open posting ↗
      </a>
    </div>
  );
}
