import { DocsShell } from "@/components/docs/DocsShell";
import styles from "../docs.module.css";

export const metadata = { title: "Consent levels (L0–L2) — mcpfor.work docs" };

const LEVELS = [
  {
    tag: "L0",
    cls: "chip--green",
    name: "Supervised — the default",
    body: "Your AI fills the application; you read the draft and click Submit yourself. Nothing is ever sent without you.",
  },
  {
    tag: "L1",
    cls: "chip--amber",
    name: "One-click approve",
    body: "You approve a single application; your AI fills and submits that one in your browser while you watch. Each one is a deliberate yes.",
  },
  {
    tag: "L2",
    cls: "chip--indigo",
    name: "Autopilot",
    body: "Under a policy you set — minimum score, daily cap, allowlisted sites — your AI works the queue in your browser session. Interruptible any time, every submission audited.",
  },
];

export default function ConsentLevelsPage() {
  return (
    <DocsShell
      slug="/docs/consent-levels"
      title="Consent levels (L0–L2)"
      lead="Graduated autonomy, always your call. You choose how much your AI does on its own — from reviewing every draft to policy-driven autopilot — and it only ever runs in your own browser."
      toc={[
        { id: "levels", label: "The three levels" },
        { id: "policy", label: "The autopilot policy" },
        { id: "browser", label: "Always your browser" },
      ]}
    >
      <section className={styles.section} id="levels">
        <h2 className={styles.h2}>The three levels</h2>
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {LEVELS.map((l) => (
            <div
              key={l.tag}
              style={{
                display: "flex",
                gap: 12,
                alignItems: "flex-start",
                border: "1px solid var(--border)",
                borderRadius: 10,
                padding: "14px 16px",
              }}
            >
              <span className={`chip ${l.cls}`} style={{ marginTop: 2 }}>
                {l.tag}
              </span>
              <div>
                <div style={{ fontWeight: 600, fontSize: 14.5 }}>{l.name}</div>
                <div style={{ fontSize: 13.5, color: "var(--ink-2)", lineHeight: 1.55, marginTop: 2 }}>
                  {l.body}
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className={styles.section} id="policy">
        <h2 className={styles.h2}>The autopilot policy</h2>
        <p className={styles.p}>
          L2 never runs unbounded. You set a minimum fit score, a maximum number of applications per
          day, and an allowlist of sites marked safe for automation. Every submission is deduplicated
          and written to your audit log. The default is L0 — autopilot is opt-in, and arriving in a
          later release.
        </p>
      </section>

      <section className={styles.section} id="browser">
        <h2 className={styles.h2}>Always your browser</h2>
        <div className={styles.note}>
          <span className={styles.noteLabel}>No dark autonomy</span>
          <span className={styles.noteBody}>
            There is never a server-side robot. Automation runs only in your own browser session,
            with your login — so there&rsquo;s no bot acting as you behind the scenes, and captchas
            are always solved by you, never bypassed.
          </span>
        </div>
      </section>
    </DocsShell>
  );
}
