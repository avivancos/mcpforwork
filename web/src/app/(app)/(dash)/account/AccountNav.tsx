"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import styles from "./account.module.css";

const ITEMS = [
  { href: "/account/autopilot", label: "Autopilot" },
  { href: "/account/billing", label: "Billing" },
  { href: "/account/data", label: "Data & privacy" },
  { href: "/account/sessions", label: "Sessions" },
];

export function AccountNav() {
  const pathname = usePathname();
  return (
    <nav className={styles.subnav} aria-label="Account">
      {ITEMS.map((i) => (
        <Link
          key={i.href}
          href={i.href}
          className={`${styles.subnavItem} ${pathname === i.href ? styles.subnavActive : ""}`}
          aria-current={pathname === i.href ? "page" : undefined}
        >
          {i.label}
        </Link>
      ))}
    </nav>
  );
}
