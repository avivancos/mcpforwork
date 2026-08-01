"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import styles from "./dash.module.css";

const ITEMS = [
  { href: "/pipeline", label: "Pipeline", also: ["/matches"] },
  { href: "/profile", label: "Profile", also: [] },
  { href: "/account/billing", label: "Account", also: ["/account"] },
];

function isActive(pathname: string, item: (typeof ITEMS)[number]): boolean {
  return [item.href, ...item.also].some((p) => pathname === p || pathname.startsWith(`${p}/`));
}

export function NavLinks() {
  const pathname = usePathname();
  return (
    <nav className={styles.nav} aria-label="Dashboard">
      {ITEMS.map((item) => (
        <Link
          key={item.href}
          href={item.href}
          className={`${styles.navItem} ${isActive(pathname, item) ? styles.navItemActive : ""}`}
          aria-current={isActive(pathname, item) ? "page" : undefined}
        >
          {item.label}
        </Link>
      ))}
    </nav>
  );
}

const TAB_ICONS: Record<string, string> = {
  Pipeline: "▦",
  Profile: "☰",
  Account: "◦",
};

export function MobileTabs() {
  const pathname = usePathname();
  return (
    <nav className={styles.tabs} aria-label="Dashboard">
      {ITEMS.map((item) => (
        <Link
          key={item.href}
          href={item.href}
          className={`${styles.tab} ${isActive(pathname, item) ? styles.tabActive : ""}`}
          aria-current={isActive(pathname, item) ? "page" : undefined}
        >
          <span className={styles.tabIcon} aria-hidden>
            {TAB_ICONS[item.label]}
          </span>
          {item.label}
        </Link>
      ))}
    </nav>
  );
}
