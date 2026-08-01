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
            const json = await requestExport();
            // The API returns the export inline — offer it as a file download
            // (self-host has no mailer to send a link with).
            const url = URL.createObjectURL(new Blob([json], { type: "application/json" }));
            const a = document.createElement("a");
            a.href = url;
            a.download = `mcpforwork-export-${new Date().toISOString().slice(0, 10)}.json`;
            a.click();
            URL.revokeObjectURL(url);
            setRequested(true);
          })
        }
      >
        {requested ? "Export downloaded ✓" : "Download JSON export"}
      </button>
      {requested && (
        <span className={styles.note}>
          {preview
            ? "Preview mode — the file contains the demo dataset, not real data."
            : "Everything — profile, matches, applications, audit trail — is in that file."}
        </span>
      )}
    </div>
  );
}

/**
 * Destructive flow — type-to-confirm before the action is even enabled
 * (security hot spot from the kickoff: GDPR-delete confirmation).
 */
export function DeleteAccount({ preview = false }: { preview?: boolean }) {
  const [confirm, setConfirm] = useState("");
  const [done, setDone] = useState(false);
  const [pending, start] = useTransition();
  const armed = confirm === "delete my account";

  if (done) {
    // The self-host API deletes IMMEDIATELY (no mailer exists to send a
    // confirmation) — the copy must not promise an email that never comes.
    return (
      <span className={styles.note}>
        {preview
          ? "Deletion requested. You’ll receive a final confirmation email — nothing is removed until you click it."
          : "Account deleted — profile, matches, applications, and audit trail are gone. This browser is signed out."}
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
