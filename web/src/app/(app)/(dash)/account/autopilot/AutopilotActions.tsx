"use client";

import { useState, useTransition } from "react";
import { revokeAutopilotPolicy, saveAutopilotPolicy } from "@/lib/actions";
import type { AutopilotPolicy } from "@/lib/api/types";
import styles from "../account.module.css";

export function PolicyForm({ current }: { current: AutopilotPolicy | null }) {
  const [minScore, setMinScore] = useState(current?.minScore ?? 75);
  const [maxPerDay, setMaxPerDay] = useState(current?.maxPerDay ?? 3);
  const [pending, start] = useTransition();

  return (
    <form
      className={styles.policyForm}
      onSubmit={(e) => {
        e.preventDefault();
        start(() => saveAutopilotPolicy({ minScore, maxPerDay }));
      }}
    >
      <label className={styles.field}>
        <span>Minimum match score (0–100)</span>
        <input
          type="number"
          className={styles.input}
          min={0}
          max={100}
          required
          value={minScore}
          onChange={(e) => setMinScore(e.target.valueAsNumber)}
        />
      </label>
      <label className={styles.field}>
        <span>Daily submit cap (1–50)</span>
        <input
          type="number"
          className={styles.input}
          min={1}
          max={50}
          required
          value={maxPerDay}
          onChange={(e) => setMaxPerDay(e.target.valueAsNumber)}
        />
      </label>
      <button type="submit" className="btn btn--primary" disabled={pending}>
        {current ? "Update policy" : "Enable autopilot"}
      </button>
    </form>
  );
}

export function RevokePolicyButton() {
  const [pending, start] = useTransition();
  return (
    <button
      type="button"
      className="btn btn--secondary"
      disabled={pending}
      onClick={() => start(() => revokeAutopilotPolicy())}
    >
      Revoke
    </button>
  );
}
