"use client";

import { useState, useTransition } from "react";
import { createBillingSession } from "@/lib/actions";
import { isSafeBillingUrl } from "@/lib/safeRedirect";
import styles from "../account.module.css";

export function BillingActions({ status }: { status: "trial" | "active" }) {
  const [unavailable, setUnavailable] = useState(false);
  const [blocked, setBlocked] = useState(false);
  const [pending, start] = useTransition();

  const go = (kind: "checkout" | "portal") =>
    start(async () => {
      setUnavailable(false);
      setBlocked(false);
      const { url } = await createBillingSession(kind);
      if (!url) {
        setUnavailable(true);
        return;
      }
      // Only ever follow an https Stripe URL — never an arbitrary redirect.
      if (isSafeBillingUrl(url)) window.location.assign(url);
      else setBlocked(true);
    });

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
        {status === "trial" ? (
          <button type="button" className="btn btn--primary" disabled={pending} onClick={() => go("checkout")}>
            {pending ? "Starting…" : "Subscribe — $5/month"}
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
      {blocked && (
        <span className={styles.gapNote}>
          That checkout link didn&rsquo;t look right, so we didn&rsquo;t follow it. Nothing was
          charged — please try again.
        </span>
      )}
    </div>
  );
}
