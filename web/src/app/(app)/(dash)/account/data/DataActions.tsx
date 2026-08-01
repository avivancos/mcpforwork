"use client";

import { useState, useTransition } from "react";
import { deleteAccount, requestExport } from "@/lib/actions";
import styles from "../account.module.css";

export function DataActions({ preview = false }: { preview?: boolean }) {
  const [requested, setRequested] = useState(false);
  const [pending, start] = useTransition();

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
      <button
        type="button"
        className="btn btn--secondary"
        disabled={pending || requested}
        onClick={() =>
          start(async () => {
            await requestExport();
            setRequested(true);
          })
        }
      >
        {requested ? "Export requested ✓" : "Request JSON export"}
      </button>
      {requested && (
        <span className={styles.note}>
          {preview
            ? "Preview mode — no email is sent. With the hosted API we'd email a download link."
            : "We'll email a download link to your address."}
        </span>
      )}
    </div>
  );
}

/**
 * Destructive flow — type-to-confirm before the action is even enabled
 * (security hot spot from the kickoff: GDPR-delete confirmation).
 */
export function DeleteAccount() {
  const [confirm, setConfirm] = useState("");
  const [done, setDone] = useState(false);
  const [pending, start] = useTransition();
  const armed = confirm === "delete my account";

  if (done) {
    return (
      <span className={styles.note}>
        Deletion requested. You&rsquo;ll receive a final confirmation email — nothing is removed
        until you click it.
      </span>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      <label className={styles.note} htmlFor="confirm-delete">
        Type <strong style={{ fontWeight: 600 }}>delete my account</strong> to confirm:
      </label>
      <input
        id="confirm-delete"
        className={styles.confirmInput}
        value={confirm}
        onChange={(e) => setConfirm(e.target.value)}
        autoComplete="off"
      />
      <button
        type="button"
        className={styles.btnDanger}
        disabled={!armed || pending}
        onClick={() =>
          start(async () => {
            await deleteAccount();
            setDone(true);
          })
        }
      >
        Delete account
      </button>
    </div>
  );
}
