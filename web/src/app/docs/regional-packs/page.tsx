import { DocsShell } from "@/components/docs/DocsShell";
import styles from "../docs.module.css";

export const metadata = { title: "Regional packs — mcpfor.work docs" };

export default function RegionalPacksPage() {
  return (
    <DocsShell
      slug="/docs/regional-packs"
      title="Regional packs"
      lead="Packs are how mcpfor.work knows every job site — any sector, any country. They're versioned data, not code, so coverage grows without waiting for a release."
      toc={[
        { id: "what", label: "What a pack contains" },
        { id: "updates", label: "Updates without reinstalling" },
        { id: "community", label: "Community & crowd-learning" },
      ]}
    >
      <section className={styles.section} id="what">
        <h2 className={styles.h2}>What a pack contains</h2>
        <p className={styles.p}>
          A pack (for example{" "}
          <span className={styles.inlineCode}>healthcare-ie</span> or{" "}
          <span className={styles.inlineCode}>logistics-de</span>) teaches your AI how each portal in
          a region or sector works: per-site search URL templates, navigation guidance for the
          browser (where the filters are, how pagination behaves, login and captcha quirks),
          apply-form field maps, and a per-site flag for whether automation is safe there.
        </p>
      </section>

      <section className={styles.section} id="updates">
        <h2 className={styles.h2}>Updates without reinstalling</h2>
        <p className={styles.p}>
          Hosted users get pack updates instantly — the connector serves the new guidance on the
          next tool call, nothing to reinstall. Self-host pulls signed, versioned packs from the
          registry:
        </p>
        <div className="term">
          <div className="term__bar">
            <span>terminal</span>
          </div>
          <div className="term__body">
            <div>
              <span className="p">$</span> mcpforwork packs update
            </div>
            <div className="a">✓ healthcare-ie v14 → v15 · logistics-de v8 (new)</div>
          </div>
        </div>
      </section>

      <section className={styles.section} id="community">
        <h2 className={styles.h2}>Community &amp; crowd-learning</h2>
        <p className={styles.p}>
          A pack is a pull request — validated in CI and test-driven against the live site. And when
          your AI successfully navigates a portal, or hits a change that breaks the playbook, it can
          report a structured diff (opt-in) that feeds the next pack version. The product learns real
          sites from real usage across everyone who opts in.
        </p>
      </section>
    </DocsShell>
  );
}
