"use client";

import { useState, useTransition } from "react";
import { updateProfile } from "@/lib/actions";
import type { Profile } from "@/lib/api/types";
import flow from "../../(flow)/flow.module.css";
import styles from "./profile.module.css";

type Tab = "required" | "deep" | "achievements" | "style";

const TABS: { key: Tab; label: string }[] = [
  { key: "required", label: "Required" },
  { key: "deep", label: "Deep" },
  { key: "achievements", label: "Achievements" },
  { key: "style", label: "Style" },
];

export function ProfileTabs({ profile }: { profile: Profile }) {
  const [tab, setTab] = useState<Tab>("required");
  const [form, setForm] = useState(profile);
  const [saved, setSaved] = useState(false);
  const [pending, start] = useTransition();

  const set = <K extends keyof Profile>(key: K, value: Profile[K]) => {
    setSaved(false);
    setForm((f) => ({ ...f, [key]: value }));
  };

  const save = () =>
    start(async () => {
      await updateProfile(form);
      setSaved(true);
    });

  return (
    <div className={styles.col}>
      <div className={styles.tabs} role="tablist" aria-label="Profile sections">
        {TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            role="tab"
            aria-selected={tab === t.key}
            className={`${styles.tab} ${tab === t.key ? styles.tabActive : ""}`}
            onClick={() => setTab(t.key)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "required" && (
        <div className={styles.card}>
          <div className={styles.cardHead}>
            <span className={styles.cardTitle}>Required — what hunting and filtering need</span>
          </div>
          <div className={flow.grid2}>
            <div className={flow.field}>
              <label className={flow.fieldLabel} htmlFor="p-name">
                Full name
              </label>
              <input id="p-name" className={flow.input} value={form.name} onChange={(e) => set("name", e.target.value)} />
            </div>
            <div className={flow.field}>
              <label className={flow.fieldLabel} htmlFor="p-email">
                Email
              </label>
              <input id="p-email" className={flow.input} value={form.email} onChange={(e) => set("email", e.target.value)} />
            </div>
          </div>
          <div className={flow.field}>
            <label className={flow.fieldLabel} htmlFor="p-role">
              Target role
            </label>
            <input id="p-role" className={flow.input} value={form.targetRole} onChange={(e) => set("targetRole", e.target.value)} />
          </div>
          <div className={flow.grid2}>
            <div className={flow.field}>
              <label className={flow.fieldLabel} htmlFor="p-rights">
                Work rights
              </label>
              <input id="p-rights" className={flow.input} value={form.workRights} onChange={(e) => set("workRights", e.target.value)} />
            </div>
            <div className={flow.field}>
              <label className={flow.fieldLabel} htmlFor="p-salary">
                Salary floor <span className={flow.fieldNote}>— private, filters only</span>
              </label>
              <input id="p-salary" className={flow.input} value={form.salaryFloor} onChange={(e) => set("salaryFloor", e.target.value)} />
            </div>
          </div>
          <div className={flow.grid2}>
            <div className={flow.field}>
              <label className={flow.fieldLabel} htmlFor="p-langs">
                Languages
              </label>
              <input id="p-langs" className={flow.input} value={form.languages} onChange={(e) => set("languages", e.target.value)} />
            </div>
            <div className={flow.field}>
              <label className={flow.fieldLabel} htmlFor="p-emp">
                Employment type
              </label>
              <input id="p-emp" className={flow.input} value={form.employmentType} onChange={(e) => set("employmentType", e.target.value)} />
            </div>
          </div>
          <div className={styles.saveRow}>
            {saved && <span className={styles.saved}>Saved ✓</span>}
            <button type="button" className="btn btn--primary" disabled={pending} onClick={save}>
              Save section
            </button>
          </div>
        </div>
      )}

      {tab === "deep" && (
        <>
          <div className={styles.card}>
            <span className={styles.cardTitle}>Deep personalization</span>
            <span style={{ fontSize: 13.5, color: "var(--ink-2)", lineHeight: 1.55 }}>
              Each unlock measurably improves output: links to scan, availability, deal-breakers,
              career narrative. Your client asks for these contextually — when a posting actually
              needs them.
            </span>
          </div>
          <div className={styles.clientBand}>
            <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 4 }}>
              <span className={styles.clientBandTitle}>Add depth in your client, not here</span>
              <span>
                Hand Claude your CV: <span className="code-chip">/profile</span> builds your facts
                inventory, achievements bank and style profile. Optional, anytime.
              </span>
            </div>
            <span className={styles.tierTag}>Tier 2 · optional</span>
          </div>
        </>
      )}

      {tab === "achievements" && (
        <div className={styles.card}>
          <div className={styles.cardHead}>
            <span className={styles.cardTitle}>Achievements bank</span>
            <span className={styles.tierTag}>{form.achievements.length} facts</span>
          </div>
          <div>
            {form.achievements.map((a) => (
              <div key={a.id} className={styles.achRow}>
                <span className={styles.achText}>{a.text}</span>
                <span className={styles.srcTag}>{a.source}</span>
              </div>
            ))}
          </div>
          <span style={{ fontSize: 12, color: "var(--ink-3)" }}>
            Drafts may only claim what&rsquo;s in this bank. New achievements are added in your
            client, where each one gets a source.
          </span>
        </div>
      )}

      {tab === "style" && (
        <div className={styles.card}>
          <span className={styles.cardTitle}>Style profile</span>
          {form.styleProfile ? (
            <span className={styles.styleQuote}>{form.styleProfile}</span>
          ) : (
            <span style={{ fontSize: 13.5, color: "var(--ink-3)" }}>
              No writing sample yet — share one in your client so drafts sound like you.
            </span>
          )}
          <span style={{ fontSize: 12, color: "var(--ink-3)" }}>
            Built from a writing sample so drafts sound like you on a good day — updated in your
            client.
          </span>
        </div>
      )}
    </div>
  );
}
