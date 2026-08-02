import { DocsShell } from "@/components/docs/DocsShell";
import styles from "../docs.module.css";

export const metadata = { title: "Slash commands — mcpfor.work docs" };

export default function SlashCommandsPage() {
  return (
    <DocsShell
      slug="/docs/slash-commands"
      title="Slash commands"
      lead="Four MCP prompts ship with the server. In clients that surface prompts as slash commands (Claude Code/Desktop, Cursor) they appear as /setup, /hunt, /review, /apply — each is a guided script that walks your agent through the phase."
      toc={[
        { id: "setup", label: "/setup" },
        { id: "hunt", label: "/hunt" },
        { id: "review", label: "/review" },
        { id: "apply", label: "/apply" },
      ]}
    >
      <section className={styles.section} id="setup">
        <h2 className={styles.h2}>/setup</h2>
        <p className={styles.p}>
          Builds your profile in under three minutes: target roles, hard constraints (salary floor,
          work mode, languages, authorization), and the first achievements of your facts inventory.
          Run it once per profile — everything else keys off it.
        </p>
      </section>

      <section className={styles.section} id="hunt">
        <h2 className={styles.h2}>/hunt</h2>
        <p className={styles.p}>
          Pulls the hunt plan for your profile, walks the source playbooks, and submits what it
          finds through the dedup gate. You get new scored matches; duplicates and reposts are
          skipped silently.
        </p>
        <div className="term">
          <div className="term__bar">
            <span>Claude</span>
          </div>
          <div className="term__body">
            <div>
              <span className="p">›</span> /hunt
            </div>
            <div className="a">12 found · 3 new · 1 duplicate skipped — seen 12 days ago</div>
          </div>
        </div>
      </section>

      <section className={styles.section} id="review">
        <h2 className={styles.h2}>/review</h2>
        <p className={styles.p}>
          Triages the matches waiting on you: fit score, why it matched, what the profile can and
          cannot prove for it. Approve the ones worth a tailored application; discard the rest with
          a reason so scoring learns nothing false.
        </p>
      </section>

      <section className={styles.section} id="apply">
        <h2 className={styles.h2}>/apply</h2>
        <p className={styles.p}>
          The supervised application loop: preflight (dedup, caps, playbook), generation brief,
          field-by-field form fill with your facts — and a hard stop at{" "}
          <code className={styles.inlineCode}>request_submit</code>, where a human confirms before
          anything is sent. Consent levels and autopilot are covered in{" "}
          <a href="/docs/consent-levels">Consent levels</a>.
        </p>
      </section>
    </DocsShell>
  );
}
