import { api } from "@/lib/api";
import dashStyles from "../../dash.module.css";
import { TopBar } from "../../TopBar";
import { AccountNav } from "../AccountNav";
import styles from "../account.module.css";
import { BillingActions } from "./BillingActions";

export const metadata = { title: "Billing — mcpfor.work" };

export default async function BillingPage({
  searchParams,
}: {
  searchParams: Promise<{ checkout?: string }>;
}) {
  const [{ checkout }, subscription] = await Promise.all([searchParams, api.getSubscription()]);
  const trial = subscription.status === "trial";
  // The self-host API reports price "self-host" — render the honest $0 card,
  // not the hosted $5 pitch (W6.1 seam fix).
  const selfHost = subscription.price === "self-host";

  return (
    <>
      <TopBar title="Account" />
      <div className={dashStyles.content}>
        <div className={styles.col}>
          <AccountNav />

          {checkout === "success" && (
            <div className={styles.successBanner}>
              <strong style={{ fontWeight: 600 }}>You&rsquo;re subscribed.</strong> Thanks for
              supporting mcpfor.work — your pipeline keeps running. Manage your plan any time below.
            </div>
          )}
          {checkout === "canceled" && (
            <div className={styles.cancelBanner}>
              Checkout canceled — no charge was made. You can subscribe whenever you&rsquo;re ready.
            </div>
          )}

          {selfHost ? (
            <div className={styles.card}>
              <span className={styles.cardTitle}>Self-host — free forever</span>
              <div className={styles.price}>
                <span className={styles.priceValue}>$0</span>
                <span className={styles.priceNote}>· your machine, your data, no account</span>
              </div>
              <div className={styles.checkList}>
                <span className={styles.checkItem}>
                  <span className={styles.checkMark}>✓</span>The full product — no feature gates
                </span>
                <span className={styles.checkItem}>
                  <span className={styles.checkMark}>✓</span>SQLite on your disk; export/delete any time
                </span>
                <span className={styles.checkItem}>
                  <span className={styles.checkMark}>✓</span>No billing to manage — there is nothing to charge
                </span>
              </div>
              <span className={styles.note}>
                The hosted $5/mo plan (sync, backups, digest email) lands with the hosted launch.
              </span>
            </div>
          ) : (
            <div className={styles.card}>
              <span className={styles.cardTitle}>
                {trial ? `Free trial — ${subscription.trialDaysLeft} days left` : "Hosted plan — active"}
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

              {trial && (
                <div className={styles.trialNudge}>
                  Your free trial ends in <strong style={{ fontWeight: 600 }}>{subscription.trialDaysLeft} days</strong>.
                  Subscribe to keep your matches, drafts, and pipeline after it&rsquo;s up — cancel any
                  time.
                </div>
              )}

              <BillingActions status={subscription.status} />
              <span className={styles.note}>
                No seats. No token markup. Your Claude or ChatGPT subscription does the thinking —
                $5 pays for infrastructure, not token resale.
              </span>
            </div>
          )}

          {!selfHost && (
            <span className={styles.note}>
              Prefer self-hosting? The full product is free forever on your machine —{" "}
              <span className="code-chip">uvx mcpforwork</span>.
            </span>
          )}
        </div>
      </div>
    </>
  );
}
