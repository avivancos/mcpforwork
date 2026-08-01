import Link from "next/link";
import { Logo } from "@/components/Logo";
import { DOCS_NAV, docGroupOf, docNeighbors, type DocSlug } from "@/app/docs/_nav";
import styles from "@/app/docs/docs.module.css";

export interface TocItem {
  id: string;
  label: string;
}

/**
 * Shared docs shell — nav + sidebar + content + on-this-page TOC + prev/next.
 * Server component: active sidebar state comes from the `slug` prop (rendered
 * per route), so no client hook is needed. Content pages stay thin.
 */
export function DocsShell({
  slug,
  title,
  lead,
  toc = [],
  children,
}: {
  slug: DocSlug;
  title: string;
  lead: string;
  toc?: TocItem[];
  children: React.ReactNode;
}) {
  const group = docGroupOf(slug);
  const { prev, next } = docNeighbors(slug);

  return (
    <div className={styles.page}>
      <div className={styles.container}>
        <nav className={styles.nav}>
          <div className={styles.navLeft}>
            <Logo />
            <Link href="/docs" className={styles.docsBadge}>
              Docs
            </Link>
          </div>
          <div className={styles.search} aria-hidden>
            <span>Search docs…</span>
            <span className={styles.kbd}>⌘K</span>
          </div>
          <div className={styles.navRight}>
            <a href="https://github.com/mcpforwork">GitHub</a>
            <Link href="/pipeline" className={styles.dashBtn}>
              Dashboard
            </Link>
          </div>
        </nav>

        <div className={styles.grid}>
          {/* sidebar */}
          <aside className={styles.sidebar} aria-label="Docs navigation">
            {DOCS_NAV.map((g) => (
              <div key={g.label} className={styles.group}>
                <span className={styles.groupLabel}>{g.label}</span>
                {g.items.map((item) => {
                  const active = item.slug === slug;
                  const soon = item.available === false;
                  const inner = (
                    <>
                      {item.name}
                      {item.count !== undefined && <span className={styles.count}>{item.count}</span>}
                      {soon && <span className={styles.soon}>soon</span>}
                    </>
                  );
                  if (soon) {
                    return (
                      <span key={item.slug} className={`${styles.item} ${styles.itemSoon}`} aria-disabled>
                        {inner}
                      </span>
                    );
                  }
                  return (
                    <Link
                      key={item.slug}
                      href={item.slug}
                      className={`${styles.item} ${active ? styles.itemActive : ""}`}
                      aria-current={active ? "page" : undefined}
                    >
                      {inner}
                    </Link>
                  );
                })}
              </div>
            ))}
          </aside>

          {/* content */}
          <main className={styles.content}>
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              <span className={styles.breadcrumb}>
                {group} <span style={{ color: "var(--border-input)" }}>/</span> <b>{title}</b>
              </span>
              <h1 className={styles.h1}>{title}</h1>
              <p className={styles.lead}>{lead}</p>
            </div>

            {children}

            {(prev || next) && (
              <div className={styles.nextGrid}>
                {prev ? (
                  <Link href={prev.slug} className={styles.nextCard}>
                    <span className={styles.nextLabel}>← Previous</span>
                    <span className={styles.nextLink}>{prev.name}</span>
                  </Link>
                ) : (
                  <span />
                )}
                {next ? (
                  <Link href={next.slug} className={`${styles.nextCard} ${styles.nextCardRight}`}>
                    <span className={styles.nextLabel}>Next →</span>
                    <span className={styles.nextLink}>{next.name}</span>
                  </Link>
                ) : (
                  <span />
                )}
              </div>
            )}
          </main>

          {/* on this page */}
          <aside className={styles.toc} aria-label="On this page">
            {toc.length > 0 && (
              <>
                <span className={styles.tocLabel}>On this page</span>
                {toc.map((t, i) => (
                  <a key={t.id} href={`#${t.id}`} className={`${styles.tocLink} ${i === 0 ? styles.tocLinkActive : ""}`}>
                    {t.label}
                  </a>
                ))}
              </>
            )}
            <div className={styles.tocFoot} style={toc.length === 0 ? { borderTop: "none", marginTop: 0 } : undefined}>
              <a href="https://github.com/mcpforwork">Edit on GitHub</a>
              <a href="https://github.com/mcpforwork/issues">Report an issue</a>
            </div>
          </aside>
        </div>
      </div>
    </div>
  );
}
