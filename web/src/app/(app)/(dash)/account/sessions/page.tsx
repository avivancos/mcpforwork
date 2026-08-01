import { api } from "@/lib/api";
import { timeAgo } from "@/lib/time";
import dashStyles from "../../dash.module.css";
import { TopBar } from "../../TopBar";
import { AccountNav } from "../AccountNav";
import styles from "../account.module.css";
import { RevokeButton } from "./RevokeButton";

export const metadata = { title: "Sessions — mcpfor.work" };

export default async function SessionsPage() {
  const sessions = await api.listSessions();

  return (
    <>
      <TopBar title="Account" />
      <div className={dashStyles.content}>
        <div className={styles.col}>
          <AccountNav />
          <div className={styles.card}>
            <span className={styles.cardTitle}>Active sign-ins</span>
            <div>
              {sessions.map((s) => (
                <div key={s.id} className={styles.row}>
                  <div>
                    <div>
                      {s.device}
                      {s.current && (
                        <span className="chip chip--green" style={{ marginLeft: 8 }}>
                          this session
                        </span>
                      )}
                    </div>
                    <div className={styles.rowSub}>Last seen {timeAgo(s.lastSeen)}</div>
                  </div>
                  {!s.current && <RevokeButton id={s.id} />}
                </div>
              ))}
            </div>
            <span className={styles.note}>
              Magic-link sign-ins only — there is no password to steal. Revoking a session signs
              that device out immediately.
            </span>
          </div>
        </div>
      </div>
    </>
  );
}
