import Link from "next/link";
import { CopyButton } from "@/components/CopyButton";
import { Logo } from "@/components/Logo";
import { Poll } from "@/components/Poll";
import { api } from "@/lib/api";
import styles from "../flow.module.css";

export const metadata = { title: "Connect your AI — mcpfor.work" };
export const dynamic = "force-dynamic";

const CONNECTOR_URL = "https://mcp.mcpfor.work/mcp";

export default async function ConnectPage() {
  const [profile, connection, subscription] = await Promise.all([
    api.getProfile(),
    api.getConnection(),
    api.getSubscription(),
  ]);

  return (
    <div className={styles.page}>
      <Poll seconds={30} />
      <header className={`${styles.topBar} ${styles.topBarBordered}`}>
        <Logo />
        <div className={styles.topBarMeta}>
          <span className={styles.email}>{profile.email}</span>
          <span className={styles.trialChip}>
            Trial · {subscription.trialDaysLeft} days left
          </span>
        </div>
      </header>

      <main className={styles.center}>
        <div className={styles.col}>
          <div className={styles.headBlock}>
            <span className="eyebrow eyebrow--accent">Setup · step 2 of 3</span>
            <h1 className={styles.h1}>Connect your AI</h1>
            <p className={styles.sub}>
              The work happens in your own Claude or ChatGPT — this dashboard just mirrors it. One
              click grants your client access; you can revoke it here anytime.
            </p>
          </div>

          {/* step 1 — done */}
          <div className={styles.step}>
            <span className={`${styles.stepDot} ${styles.stepDotDone}`} aria-hidden>
              ✓
            </span>
            <div className={styles.stepText}>
              <span className={`${styles.stepTitle} ${styles.stepTitleMuted}`}>Signed in</span>
              <span className={`${styles.stepSub} ${styles.stepSubFaint}`}>
                Magic link verified · {profile.email}
              </span>
            </div>
          </div>

          {/* step 2 — active */}
          <div className={styles.step}>
            <span className={`${styles.stepDot} ${styles.stepDotActive}`}>2</span>
            <div className={styles.stepBody}>
              <div className={styles.stepText}>
                <span className={styles.stepTitle}>Connect your client</span>
                <span className={styles.stepSub}>
                  Pick where you already chat. You&rsquo;ll approve the connection there — standard
                  OAuth, nothing to install.
                </span>
              </div>
              <div className={styles.clients}>
                <div className={`${styles.clientCard} ${styles.clientCardHero}`}>
                  <span className={styles.clientName}>
                    <span className={styles.clientDot} style={{ background: "var(--claude-dot)" }} />
                    Claude
                  </span>
                  <span className={styles.clientSub}>claude.ai, Desktop &amp; mobile apps</span>
                  <a
                    href="https://claude.ai/settings/connectors"
                    className={`btn--primary ${styles.clientCta}`}
                    style={{ fontWeight: 600, display: "block" }}
                  >
                    Connect to Claude
                  </a>
                </div>
                <div className={styles.clientCard}>
                  <span className={styles.clientName}>
                    <span className={styles.clientDot} style={{ background: "var(--chatgpt-dot)" }} />
                    ChatGPT
                  </span>
                  <span className={styles.clientSub}>chatgpt.com &amp; desktop app</span>
                  <a
                    href="https://chatgpt.com"
                    className={`btn--secondary ${styles.clientCta}`}
                    style={{ display: "block" }}
                  >
                    Connect to ChatGPT
                  </a>
                </div>
              </div>
              <div className={styles.urlRow}>
                <span className={styles.url}>{CONNECTOR_URL}</span>
                <CopyButton text={CONNECTOR_URL} className={styles.copyBtn} label="Copy URL" />
              </div>
              <span className={styles.hint}>
                Other MCP client? Paste the connector URL into its custom-connector settings.
              </span>
            </div>
          </div>

          {/* step 3 — pending / done */}
          <div className={styles.step}>
            <span
              className={`${styles.stepDot} ${connection.connected ? styles.stepDotDone : styles.stepDotPending}`}
              aria-hidden
            >
              {connection.connected ? "✓" : "3"}
            </span>
            <div className={styles.stepText}>
              <span
                className={`${styles.stepTitle} ${connection.connected ? "" : styles.stepTitleFaint}`}
              >
                Say hello
              </span>
              <span className={`${styles.stepSub} ${styles.stepSubFaint}`}>
                {connection.connected
                  ? `First call received from ${connection.client}. Next: a 3-minute profile.`
                  : "We'll confirm here the moment your client makes its first call. Then: a 3-minute profile."}
              </span>
            </div>
          </div>

          <div className={styles.foot}>
            {connection.connected ? (
              <>
                <span className={styles.footStatus}>
                  <span className="dot dot--ok" /> Connected · {connection.client}
                </span>
                <Link href="/onboarding" className={styles.footLink}>
                  Continue to your profile →
                </Link>
              </>
            ) : (
              <>
                <span className={styles.footStatus}>
                  <span className="dot dot--hollow" /> Not connected yet — this page updates when you
                  are
                </span>
                <a href="https://github.com/mcpforwork" className={styles.footLink}>
                  Prefer self-hosting? It&rsquo;s free →
                </a>
              </>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
