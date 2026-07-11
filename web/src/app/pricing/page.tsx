import Link from "next/link";
import { Logo } from "@/components/Logo";
import styles from "./pricing.module.css";

export const metadata = {
  title: "Pricing — mcpfor.work",
  description: "Self-host free forever, or hosted at a flat $5/month after a 7-day free trial. One plan, no tiers, no seats — you bring the AI in both.",
};

export default function PricingPage() {
  return (
    <div className={styles.page}>
      <nav className={styles.nav}>
        <Logo size={16} />
        <div className={styles.navRight}>
          <Link href="/docs">Docs</Link>
          <Link href="/faq">FAQ</Link>
          <a href="https://github.com/mcpforwork">GitHub</a>
        </div>
      </nav>

      <div className={styles.container}>
        <header className={styles.head}>
          <span className="eyebrow eyebrow--accent">Pricing</span>
          <h1 className={styles.h1}>Same product. You bring the AI in both.</h1>
          <p className={styles.lead}>
            The intelligence runs in your own Claude or ChatGPT. That&rsquo;s why hosted is $5, not
            $50 — it&rsquo;s infrastructure, not token resale.
          </p>
        </header>

        <div className={styles.grid}>
          <div className={styles.card}>
            <span className={styles.name}>Self-host</span>
            <div className={styles.priceLine}>
              <span className={styles.priceValue}>Free</span>
              <span className={styles.priceNote}>forever · Apache-2.0</span>
            </div>
            <div className={styles.checks}>
              <span className={styles.check}>
                <b>✓</b>The full product — open-core parity
              </span>
              <span className={styles.check}>
                <b>✓</b>Your machine, SQLite, your data
              </span>
              <span className={styles.check}>
                <b>✓</b>All packs, all consent levels
              </span>
            </div>
            <div className={styles.term}>
              <span style={{ color: "var(--term-muted)" }}>$</span> uvx mcpforwork
            </div>
          </div>

          <div className={`${styles.card} ${styles.cardHero}`}>
            <span className={styles.badge}>Hosted</span>
            <span className={styles.name}>Hosted</span>
            <div className={styles.priceLine}>
              <span className={styles.priceValue}>$5</span>
              <span className={styles.priceNote}>/month · after a 7-day free trial</span>
            </div>
            <div className={styles.checks}>
              <span className={styles.check}>
                <b>✓</b>Nothing to install — connect from claude.ai
              </span>
              <span className={styles.check}>
                <b>✓</b>Sync, backups, live pack updates
              </span>
              <span className={styles.check}>
                <b>✓</b>Web dashboard + daily digest email
              </span>
            </div>
            <Link href="/connect" className={styles.cta}>
              Start free trial
            </Link>
          </div>
        </div>

        <p className={styles.foot}>
          One plan, no tiers, no seats. Magic-link sign-in — no password, ever. Cancel any time.
          <br />
          Questions? See the <Link href="/faq">FAQ</Link>.
        </p>
      </div>
    </div>
  );
}
