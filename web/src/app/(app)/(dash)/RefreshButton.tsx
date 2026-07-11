"use client";

import { useRouter } from "next/navigation";
import { useTransition } from "react";
import styles from "./dash.module.css";

/**
 * Manual refresh button. Background polling lives in <Poll> (rendered by
 * TopBar) so the freshness policy has one home — brief §6: no realtime/SSE.
 */
export function RefreshButton() {
  const router = useRouter();
  const [pending, startTransition] = useTransition();

  return (
    <button
      type="button"
      className={styles.refreshBtn}
      onClick={() => startTransition(() => router.refresh())}
      disabled={pending}
    >
      ↻ Refresh
    </button>
  );
}
