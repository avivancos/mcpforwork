import { Logo } from "@/components/Logo";
import { api } from "@/lib/api";
import { MobileTabs, NavLinks } from "./NavLinks";
import styles from "./dash.module.css";

// The dashboard is per-user and reads live state through the API seam — never
// prerender it, or a fixtures-built artifact would serve baked demo pages
// after MCPFORWORK_API_URL is set (ADR 0002's config-swap contract).
export const dynamic = "force-dynamic";

export default async function DashLayout({ children }: { children: React.ReactNode }) {
  const [connection, subscription] = await Promise.all([api.getConnection(), api.getSubscription()]);

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
              <span className="dot dot--ok" /> Supervised
            </span>
            <span className={styles.autonomyHint}>You click Submit. Autopilot: coming later.</span>
          </div>
          <span className={styles.trialLine}>
            Trial · {subscription.trialDaysLeft} days left ·{" "}
            <span className={styles.trialPrice}>{subscription.price}</span>
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
