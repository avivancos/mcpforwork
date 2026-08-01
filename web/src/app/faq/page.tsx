import Link from "next/link";
import { Logo } from "@/components/Logo";
import { FAQ_GROUPS } from "@/content/faq";
import styles from "./faq.module.css";

export const metadata = {
  title: "FAQ — mcpfor.work",
  description:
    "Fair questions about mcpfor.work: how it works, your data and privacy, and the flat $5/mo pricing.",
};

export default function FaqPage() {
  return (
    <div className={styles.page}>
      <nav className={styles.nav}>
        <Logo size={16} />
        <div className={styles.navRight}>
          <Link href="/docs">Docs</Link>
          <a href="https://github.com/mcpforwork">GitHub</a>
          <Link href="/connect" className={styles.dashBtn}>
            Connect
          </Link>
        </div>
      </nav>

      <div className={styles.container}>
        <header className={styles.head}>
          <span className="eyebrow eyebrow--accent">FAQ</span>
          <h1 className={styles.h1}>Fair questions</h1>
          <p className={styles.lead}>
            The honest answers — how it works, what happens to your data, and why it&rsquo;s $5.
          </p>
        </header>

        {FAQ_GROUPS.map((group) => (
          <section key={group.label} className={styles.group}>
            <span className={styles.groupLabel}>{group.label}</span>
            {group.items.map((item) => (
              <div key={item.q} className={styles.item}>
                <span className={styles.q}>{item.q}</span>
                <span className={styles.a}>{item.a}</span>
              </div>
            ))}
          </section>
        ))}

        <div className={styles.cta}>
          <span className={styles.ctaTitle}>Still have a question?</span>
          <span className={styles.ctaText}>
            The docs go deeper, or email us — a real person answers.
          </span>
          <div className={styles.ctaRow}>
            <Link href="/docs" className={styles.ctaPrimary}>
              Read the docs
            </Link>
            <a href="mailto:hello@mcpfor.work" className={styles.ctaSecondary}>
              Email us
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}
