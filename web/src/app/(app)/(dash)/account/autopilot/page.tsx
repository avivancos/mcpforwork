import { api } from "@/lib/api";
import { timeAgo } from "@/lib/time";
import dashStyles from "../../dash.module.css";
import { TopBar } from "../../TopBar";
import { AccountNav } from "../AccountNav";
import styles from "../account.module.css";
import { PolicyForm, RevokePolicyButton } from "./AutopilotActions";

export const metadata = { title: "Autopilot — mcpfor.work" };

export default async function AutopilotPage() {
  const [policy, boards] = await Promise.all([api.getAutopilotPolicy(), api.getAutopilotBoards()]);

  return (
    <>
      <TopBar title="Account" />
      <div className={dashStyles.content}>
        <div className={styles.col}>
          <AccountNav />
          <div className={styles.card}>
            <span className={styles.cardTitle}>Autopilot (L2)</span>
            {policy ? (
              <>
                <div className={styles.row}>
                  <div>
                    <div>
                      Policy active
                      <span className="chip chip--green" style={{ marginLeft: 8 }}>
                        enabled
                      </span>
                    </div>
                    <div className={styles.rowSub}>
                      Min score {policy.minScore} · up to {policy.maxPerDay} submits/day · recorded{" "}
                      {timeAgo(policy.createdAt)}
                    </div>
                  </div>
                  <RevokePolicyButton />
                </div>
                <span className={styles.note}>
                  Revoking stops new auto-submits immediately: the next submit decision comes back
                  to you. Applications already authorized before revocation are not recalled — your
                  agent may still be mid-submit on one.
                </span>
              </>
            ) : (
              <span className={styles.note}>
                Autopilot is off — every submit is yours. Your agent prepares each application and
                pauses for your approval (L0), or you approve submits one by one from a match page
                (L1).
              </span>
            )}
          </div>

          <div className={styles.card}>
            <span className={styles.cardTitle}>
              {policy ? "Update policy" : "Enable autopilot"}
            </span>
            <div className={styles.gapNote}>
              With this policy, your agent may submit an application{" "}
              <strong>without asking you each time</strong> when all of these hold: the board is
              verified safe for auto-apply, the match scores at or above your minimum, and your
              daily cap is not reached. Every auto-submit is recorded in your audit log with the
              policy criteria that authorized it. You can revoke this at any time — revocation
              takes effect on the next submit decision.
            </div>
            <PolicyForm current={policy} />
          </div>

          <div className={styles.card}>
            <span className={styles.cardTitle}>Boards verified safe for auto-apply</span>
            {boards.length > 0 ? (
              <div>
                {boards.map((b) => (
                  <div key={b.slug} className={styles.row}>
                    <div>
                      <div>{b.name}</div>
                      <div className={styles.rowSub}>{b.slug}</div>
                    </div>
                    <span className="chip chip--green">auto_apply_safe</span>
                  </div>
                ))}
              </div>
            ) : (
              <span className={styles.note}>
                None yet. A board only appears here after a human has browser-verified its apply
                flow and its pack is flagged <code>auto_apply_safe</code> — until then autopilot
                authorizes nothing, whatever your policy says.
              </span>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
