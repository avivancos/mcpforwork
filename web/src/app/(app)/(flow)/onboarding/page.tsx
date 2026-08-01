import Link from "next/link";
import { Logo } from "@/components/Logo";
import { api } from "@/lib/api";
import styles from "../flow.module.css";
import { Wizard } from "./Wizard";

export const metadata = { title: "Your profile — mcpfor.work" };
export const dynamic = "force-dynamic";

export default async function OnboardingPage() {
  const profile = await api.getProfile();

  return (
    <div className={styles.page}>
      <header className={styles.topBar}>
        <Logo />
        <Link href="/pipeline" className={styles.skip}>
          Skip for now — finish later in your client
        </Link>
      </header>
      <main className={styles.center} style={{ paddingTop: 32 }}>
        <Wizard profile={profile} />
      </main>
    </div>
  );
}
