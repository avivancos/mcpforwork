"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { updateProfile } from "@/lib/actions";
import type { Profile } from "@/lib/api/types";
import styles from "../flow.module.css";

const STEPS = [
  {
    n: 1,
    title: "Who you are",
    sub: "Identity for your assets and applications. Never shared without a submit you approve.",
    time: "~3 minutes",
  },
  {
    n: 2,
    title: "What are you looking for?",
    sub: "These become hard filters — every match is scored against them. Nothing here is shared with employers.",
    time: "~90 seconds left",
  },
  {
    n: 3,
    title: "Hard constraints",
    sub: "The deal-breakers your AI applies before you ever see a match.",
    time: "~30 seconds left",
  },
] as const;

export function Wizard({ profile }: { profile: Profile }) {
  const router = useRouter();
  const [pending, start] = useTransition();
  const [step, setStep] = useState<number>(Math.min(profile.tier1Step, 3));
  const [form, setForm] = useState({
    name: profile.name,
    email: profile.email,
    headline: profile.headline,
    targetRole: profile.targetRole,
    cities: profile.cities,
    workRights: profile.workRights,
    salaryFloor: profile.salaryFloor,
    workMode: profile.workMode,
    languages: profile.languages,
    seniority: profile.seniority,
    employmentType: profile.employmentType,
  });
  const [cityDraft, setCityDraft] = useState("");

  const meta = STEPS[step - 1];
  const set = <K extends keyof typeof form>(key: K, value: (typeof form)[K]) =>
    setForm((f) => ({ ...f, [key]: value }));

  const addCity = () => {
    const city = cityDraft.trim();
    const exists = form.cities.some((c) => c.toLowerCase() === city.toLowerCase());
    if (city && !exists) set("cities", [...form.cities, city]);
    setCityDraft("");
  };

  const save = () =>
    start(async () => {
      // Never regress progress: Back-then-Continue must not lower tier1Step.
      const nextStep = Math.max(profile.tier1Step, Math.min(step + 1, 4)) as Profile["tier1Step"];
      await updateProfile({ ...form, tier1Step: nextStep });
      if (step < 3) setStep(step + 1);
      else router.push("/pipeline");
    });

  return (
    <div className={styles.colWide + " " + styles.col}>
      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <div className={styles.progressHead}>
          <span className={styles.progressStep}>Your profile · step {step} of 3</span>
          <span>{meta.time}</span>
        </div>
        <div className={styles.segments} role="progressbar" aria-valuemin={1} aria-valuemax={3} aria-valuenow={step}>
          {[1, 2, 3].map((n) => (
            <span key={n} className={`${styles.segment} ${n <= step ? styles.segmentDone : ""}`} />
          ))}
        </div>
      </div>

      <div className={styles.headBlock} style={{ gap: 8 }}>
        <h1 className={styles.h1} style={{ fontSize: 30 }}>
          {meta.title}
        </h1>
        <p className={styles.sub} style={{ fontSize: 14.5 }}>
          {meta.sub}
        </p>
      </div>

      <div className={styles.formCard}>
        {step === 1 && (
          <>
            <div className={styles.field}>
              <label className={styles.fieldLabel} htmlFor="name">
                Full name
              </label>
              <input
                id="name"
                className={styles.input}
                value={form.name}
                onChange={(e) => set("name", e.target.value)}
              />
            </div>
            <div className={styles.grid2}>
              <div className={styles.field}>
                <label className={styles.fieldLabel} htmlFor="email">
                  Email
                </label>
                <input
                  id="email"
                  type="email"
                  className={styles.input}
                  value={form.email}
                  onChange={(e) => set("email", e.target.value)}
                />
              </div>
              <div className={styles.field}>
                <label className={styles.fieldLabel} htmlFor="headline">
                  One-line background
                </label>
                <input
                  id="headline"
                  className={styles.input}
                  placeholder="ICU Nurse · 6 yrs · Madrid"
                  value={form.headline}
                  onChange={(e) => set("headline", e.target.value)}
                />
              </div>
            </div>
          </>
        )}

        {step === 2 && (
          <>
            <div className={styles.field}>
              <label className={styles.fieldLabel} htmlFor="role">
                Target role
              </label>
              <input
                id="role"
                className={styles.input}
                autoFocus
                value={form.targetRole}
                onChange={(e) => set("targetRole", e.target.value)}
              />
            </div>
            <div className={styles.grid2}>
              <div className={styles.field}>
                <label className={styles.fieldLabel} htmlFor="city">
                  Where
                </label>
                <div className={styles.chipsInput}>
                  {form.cities.map((city) => (
                    <span key={city} className={styles.cityChip}>
                      {city}
                      <button
                        type="button"
                        aria-label={`Remove ${city}`}
                        onClick={() => set("cities", form.cities.filter((c) => c !== city))}
                      >
                        ×
                      </button>
                    </span>
                  ))}
                  <input
                    id="city"
                    placeholder="Add city…"
                    value={cityDraft}
                    onChange={(e) => setCityDraft(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        e.preventDefault();
                        addCity();
                      }
                    }}
                    onBlur={addCity}
                  />
                </div>
              </div>
              <div className={styles.field}>
                <label className={styles.fieldLabel} htmlFor="rights">
                  Work rights
                </label>
                <select
                  id="rights"
                  className={styles.input}
                  value={form.workRights}
                  onChange={(e) => set("workRights", e.target.value)}
                >
                  <option>EU citizen — no visa needed</option>
                  <option>Visa / permit required</option>
                  <option>Sponsorship needed</option>
                </select>
              </div>
            </div>
            <div className={styles.grid2}>
              <div className={styles.field}>
                <label className={styles.fieldLabel} htmlFor="salary">
                  Salary floor <span className={styles.fieldNote}>— private, filters only</span>
                </label>
                <input
                  id="salary"
                  className={styles.input}
                  value={form.salaryFloor}
                  onChange={(e) => set("salaryFloor", e.target.value)}
                />
              </div>
              <div className={styles.field}>
                <span className={styles.fieldLabel}>On-site / remote</span>
                <div className={styles.segmented} role="radiogroup" aria-label="Work mode">
                  {(
                    [
                      ["onsite", "On-site OK"],
                      ["hybrid", "Hybrid"],
                      ["remote", "Remote"],
                    ] as const
                  ).map(([key, label]) => (
                    <button
                      key={key}
                      type="button"
                      role="radio"
                      aria-checked={form.workMode === key}
                      className={`${styles.segmentedOpt} ${form.workMode === key ? styles.segmentedOptActive : ""}`}
                      onClick={() => set("workMode", key)}
                    >
                      {label}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </>
        )}

        {step === 3 && (
          <>
            <div className={styles.grid2}>
              <div className={styles.field}>
                <label className={styles.fieldLabel} htmlFor="languages">
                  Languages
                </label>
                <input
                  id="languages"
                  className={styles.input}
                  value={form.languages}
                  onChange={(e) => set("languages", e.target.value)}
                />
              </div>
              <div className={styles.field}>
                <label className={styles.fieldLabel} htmlFor="seniority">
                  Seniority
                </label>
                <select
                  id="seniority"
                  className={styles.input}
                  value={form.seniority}
                  onChange={(e) => set("seniority", e.target.value)}
                >
                  <option>Entry</option>
                  <option>Mid</option>
                  <option>Senior</option>
                  <option>Lead</option>
                  <option>Exec</option>
                </select>
              </div>
            </div>
            <div className={styles.field}>
              <label className={styles.fieldLabel} htmlFor="employment">
                Employment type
              </label>
              <select
                id="employment"
                className={styles.input}
                value={form.employmentType}
                onChange={(e) => set("employmentType", e.target.value)}
              >
                <option>Full-time</option>
                <option>Contract</option>
                <option>Part-time</option>
                <option>Freelance</option>
              </select>
            </div>
          </>
        )}
      </div>

      <div className={styles.wizNav}>
        {step > 1 ? (
          <button type="button" className={styles.back} onClick={() => setStep(step - 1)}>
            ← Back
          </button>
        ) : (
          <span />
        )}
        <button type="button" className={styles.continue} onClick={save} disabled={pending}>
          {step === 3 ? "Finish" : "Continue"}
        </button>
      </div>

      <div className={styles.laterBand}>
        <span className={styles.laterTag}>Later</span>
        <span>
          Depth comes after: hand your CV to your client and it builds your{" "}
          <strong style={{ fontWeight: 600, color: "var(--ink-label)" }}>facts inventory</strong> —
          the only source drafts may claim from. Optional, anytime.
        </span>
      </div>
    </div>
  );
}
