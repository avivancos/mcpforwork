"use client";

import { useTransition } from "react";
import { approveMatch, approveSubmit, discardMatch, restoreMatch } from "@/lib/actions";
import type { Stage } from "@/lib/api/types";
import styles from "./match.module.css";

export function MatchActions({
  id,
  stage,
  postingUrl,
  applicationId,
}: {
  id: string;
  stage: Stage;
  postingUrl: string;
  applicationId: string | null;
}) {
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
        <>
          {applicationId && (
            <>
              <button
                type="button"
                className="btn btn--primary"
                disabled={pending}
                onClick={() => start(() => approveSubmit(applicationId, id))}
              >
                Approve submit
              </button>
              <p className={styles.approveNote}>
                Approving authorizes your agent to click Submit once — for this application only.
                The decision is recorded in the audit log below.
              </p>
            </>
          )}
          <a href="https://claude.ai" className={applicationId ? "btn btn--secondary" : "btn btn--primary"}>
            Review in Claude →
          </a>
        </>
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
