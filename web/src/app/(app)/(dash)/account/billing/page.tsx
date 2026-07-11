import { api } from "@/lib/api";
import dashStyles from "../../dash.module.css";
import { TopBar } from "../../TopBar";
import { AccountNav } from "../AccountNav";
import styles from "../account.module.css";
import { BillingActions } from "./BillingActions";

export const metadata = { title: "Billing — mcpfor.work" };

export default async function BillingPage() {
  const subscription = await api.getSubscription();

  return (
    <>
      <TopBar title="Account" />
      <div className={dashStyles.content}>
        <div className={styles.col}>
          <AccountNav />
          <div className={styles.card}>
            <span className={styles.cardTitle}>
              {subscription.status === "trial"
                ? `Free trial — ${subscription.trialDaysLeft} days left`
                : "Hosted plan"}
            </span>
            <div className={styles.price}>
              <span className={styles.priceValue}>$5</span>
              <span className={styles.priceNote}>/month flat · one plan, no tiers</span>
            </div>
            <div className={styles.checkList}>
              <span className={styles.checkItem}>
                <span className={styles.checkMark}>✓</span>Nothing to install — connect from claude.ai
              </span>
              <span className={styles.checkItem}>
                <span className={styles.checkMark}>✓</span>Sync, backups, live pack updates
              </span>
              <span className={styles.checkItem}>
                <span className={styles.checkMark}>✓</span>Web dashboard + daily digest email
              </span>
            </div>
            <BillingActions status={subscription.status} />
            <span className={styles.note}>
              No seats. No token markup. Your Claude or ChatGPT subscription does the thinking —
              $5 pays for infrastructure, not token resale.
            </span>
          </div>
          <span className={styles.note}>
            Prefer self-hosting? The full product is free forever on your machine —{" "}
            <span className="code-chip">uvx mcpforwork</span>.
          </span>
        </div>
      </div>
    </>
  );
}
