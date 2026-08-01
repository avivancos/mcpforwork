import { Logo } from "@/components/Logo";
import { usingFixtures } from "@/lib/api";
import styles from "../flow.module.css";
import { LoginForm } from "./LoginForm";

export const metadata = { title: "Sign in — mcpfor.work" };

export default function LoginPage() {
  return (
    <div className={styles.page}>
      <header className={styles.topBar}>
        <Logo />
        <a href="/" className={styles.skip}>
          ← Back to mcpfor.work
        </a>
      </header>
      <main className={styles.center} style={{ paddingTop: 96 }}>
        <div className={styles.col} style={{ maxWidth: 440 }}>
          <div className={styles.headBlock}>
            <span className="eyebrow eyebrow--accent">Setup · step 1 of 3</span>
            <h1 className={styles.h1}>Sign in</h1>
            <p className={styles.sub}>
              A magic link, no password — ever. We email you a one-time sign-in link.
            </p>
          </div>
          <LoginForm preview={usingFixtures} />

        </div>
      </main>
    </div>
  );
}
