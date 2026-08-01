"use client";

import { useState, useTransition } from "react";
import { requestMagicLink } from "@/lib/actions";
import styles from "../flow.module.css";

export function LoginForm({ preview = false }: { preview?: boolean }) {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [pending, start] = useTransition();

  if (sent) {
    return (
      <div className={styles.formCard} style={{ gap: 10 }}>
        <span className={styles.stepTitle}>Check your inbox</span>
        <span className={styles.stepSub}>
          {preview ? (
            <>
              Preview mode — no email is actually sent. With the hosted API a sign-in link would go
              to <strong style={{ fontWeight: 600 }}>{email}</strong>, expiring in 15 minutes.
            </>
          ) : (
            <>
              We sent a sign-in link to <strong style={{ fontWeight: 600 }}>{email}</strong>. It
              expires in 15 minutes.
            </>
          )}{" "}
          Wrong address?{" "}
          <button type="button" onClick={() => setSent(false)} style={{ color: "var(--link-green)", fontWeight: 500 }}>
            Try again
          </button>
        </span>
      </div>
    );
  }

  return (
    <form
      className={styles.formCard}
      onSubmit={(e) => {
        e.preventDefault();
        start(async () => {
          await requestMagicLink(email);
          setSent(true);
        });
      }}
    >
      <div className={styles.field}>
        <label className={styles.fieldLabel} htmlFor="email">
          Email
        </label>
        <input
          id="email"
          type="email"
          required
          autoFocus
          className={styles.input}
          placeholder="you@example.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
      </div>
      <button type="submit" className={styles.continue} disabled={pending || !email}>
        Send magic link
      </button>
    </form>
  );
}
