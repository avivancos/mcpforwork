import { DocsShell } from "@/components/docs/DocsShell";
import styles from "../docs.module.css";

export const metadata = { title: "Contribute a pack — mcpfor.work docs" };

export default function ContributeAPackPage() {
  return (
    <DocsShell
      slug="/docs/contribute-a-pack"
      title="Contribute a pack"
      lead="Sector and country knowledge is data, not code: source packs are versioned YAML files that ship with the repo and load at startup. Adding a board for your country means writing YAML, not Python."
      toc={[
        { id: "schema", label: "The pack schema" },
        { id: "validate", label: "Validate locally" },
        { id: "pr", label: "Open the PR" },
      ]}
    >
      <section className={styles.section} id="schema">
        <h2 className={styles.h2}>The pack schema</h2>
        <p className={styles.p}>
          Packs live in <code className={styles.inlineCode}>src/mcpforwork/packs/*.yaml</code> —
          one file per country or remote-global pack. A pack declares its sources with everything
          the hunt pipeline needs to search them:
        </p>
        <div className="term">
          <div className="term__bar">
            <span>de.yaml</span>
          </div>
          <div className="term__body">
            <div>pack: {"{ id: de, version: 1, kind: country, title: Germany job boards }"}</div>
            <div>sources:</div>
            <div>&nbsp;&nbsp;- slug: indeed-de</div>
            <div>&nbsp;&nbsp;&nbsp;&nbsp;base_url: https://de.indeed.com</div>
            <div>&nbsp;&nbsp;&nbsp;&nbsp;countries: [DE] · sectors: [any] · tier: free</div>
            <div>&nbsp;&nbsp;&nbsp;&nbsp;search_playbook: {"{ url_template: …, result_hint: … }"}</div>
          </div>
        </div>
        <p className={styles.p}>
          The <code className={styles.inlineCode}>search_playbook</code> is the valuable part: the
          URL template and pagination hints your agent follows to search the board. Slugs must be
          unique across all packs.
        </p>
      </section>

      <section className={styles.section} id="validate">
        <h2 className={styles.h2}>Validate locally</h2>
        <p className={styles.p}>
          Packs are validated against the domain schema at import time — a malformed pack raises
          instead of shipping silently, and the test suite loads every shipped pack. Run{" "}
          <code className={styles.inlineCode}>uv run pytest</code> after editing; then probe the
          playbook for real with <code className={styles.inlineCode}>source_playbook</code> and a
          manual search in your agent client.
        </p>
      </section>

      <section className={styles.section} id="pr">
        <h2 className={styles.h2}>Open the PR</h2>
        <p className={styles.p}>
          One YAML file, one PR. Include a sample search URL that worked when you probed it — that
          is the live-probe evidence reviewers ask for. If a shipped board changes its markup,
          report it from your client with{" "}
          <code className={styles.inlineCode}>report_playbook_result</code> so the pack can be
          fixed forward.
        </p>
      </section>
    </DocsShell>
  );
}
