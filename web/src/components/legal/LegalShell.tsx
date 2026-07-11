import Link from "next/link";
import { Logo } from "@/components/Logo";
import styles from "./legal.module.css";

/**
 * Shared shell for the legal pages — nav + a visible "draft, pending counsel
 * review" banner + title/updated + prose. `updated` is a static string passed
 * per page (never new Date()) so builds stay reproducible.
 */
export function LegalShell({
  title,
  updated,
  lead,
  children,
}: {
  title: string;
  updated: string;
  lead: string;
  children: React.ReactNode;
}) {
  return (
    <div className={styles.page}>
      <nav className={styles.nav}>
        <Logo size={16} />
        <div className={styles.navRight}>
          <Link href="/docs">Docs</Link>
          <Link href="/faq">FAQ</Link>
          <Link href="/">Home</Link>
        </div>
      </nav>

      <div className={styles.container}>
        <div className={styles.draft}>
          <span className={styles.draftLabel}>Draft</span>
          <span>
            This is a plain-language draft describing how the product is designed to work. It has
            not yet been reviewed by counsel and is not the final agreement — it will be finalized
            before the hosted service launches.
          </span>
        </div>

        <header className={styles.head}>
          <h1 className={styles.h1}>{title}</h1>
          <span className={styles.updated}>Last updated: {updated}</span>
          <p className={styles.lead}>{lead}</p>
        </header>

        <div className={styles.prose}>{children}</div>

        <div className={styles.crossLinks}>
          <Link href="/privacy">Privacy</Link>
          <Link href="/terms">Terms</Link>
          <Link href="/security">Security</Link>
          <a href="mailto:hello@mcpfor.work">Contact</a>
        </div>
      </div>
    </div>
  );
}
