"use client";

import { useState, useTransition } from "react";
import { createBillingSession } from "@/lib/actions";
import styles from "../account.module.css";

export function BillingActions({ status }: { status: "trial" | "active" }) {
  const [unavailable, setUnavailable] = useState(false);
  const [pending, start] = useTransition();

  const go = (kind: "checkout" | "portal") =>
    start(async () => {
      const { url } = await createBillingSession(kind);
      if (url) window.location.assign(url);
      else setUnavailable(true);
    });

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
        {status === "trial" ? (
          <button type="button" className="btn btn--primary" disabled={pending} onClick={() => go("checkout")}>
            Start subscription
          </button>
        ) : (
          <button type="button" className="btn btn--secondary" disabled={pending} onClick={() => go("portal")}>
            Manage in Stripe portal
          </button>
        )}
      </div>
      {unavailable && (
        <span className={styles.gapNote}>
          Billing isn&rsquo;t wired up yet in this preview — Stripe checkout lands with the hosted
          API (S7.1). Nothing was charged.
        </span>
      )}
    </div>
  );
}
