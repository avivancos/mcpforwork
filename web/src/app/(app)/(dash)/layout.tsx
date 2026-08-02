import { Logo } from "@/components/Logo";
import { api } from "@/lib/api";
import { MobileTabs, NavLinks } from "./NavLinks";
import styles from "./dash.module.css";

// The dashboard is per-user and reads live state through the API seam — never
// prerender it, or a fixtures-built artifact would serve baked demo pages
// after MCPFORWORK_API_URL is set (ADR 0002's config-swap contract).
export const dynamic = "force-dynamic";

export default async function DashLayout({ children }: { children: React.ReactNode }) {
  const [connection, subscription, policy] = await Promise.all([
    api.getConnection(),
    api.getSubscription(),
    api.getAutopilotPolicy(),
  ]);

  return (
    <div className={styles.shell}>
      <aside className={styles.sidebar}>
        <span className={styles.sidebarLogo}>
          <Logo size={14.5} href="/pipeline" />
        </span>
        <NavLinks />
        <div className={styles.sidebarFoot}>
          <div className={styles.autonomyCard}>
            <span className={styles.autonomyLabel}>Autonomy</span>
            <span className={styles.autonomyState}>
              <span className="dot dot--ok" /> {policy ? "Autopilot L2" : "Supervised"}
            </span>
            <span className={styles.autonomyHint}>
              {policy
                ? `Auto-submits on verified-safe boards · score ≥ ${policy.minScore} · ≤ ${policy.maxPerDay}/day.`
                : "You click Submit — or enable autopilot in Account."}
            </span>
          </div>
          <span className={styles.trialLine}>
            {subscription.price === "self-host" ? (
              "Self-host · free forever"
            ) : subscription.status === "trial" ? (
              <>
                Trial · {subscription.trialDaysLeft} days left ·{" "}
                <span className={styles.trialPrice}>{subscription.price}</span>
              </>
            ) : (
              <span className={styles.trialPrice}>{subscription.price}</span>
            )}
          </span>
        </div>
      </aside>

      <div className={styles.main}>
        <header className={styles.mobileHeader}>
          <Logo size={14} href="/pipeline" />
          {connection.connected && (
            <span className={styles.connChip} style={{ fontSize: 11, padding: "3px 9px" }}>
              <span className="dot dot--ok" style={{ width: 6, height: 6 }} /> {connection.client}
            </span>
          )}
        </header>
        {children}
      </div>

      <MobileTabs />
    </div>
  );
}
