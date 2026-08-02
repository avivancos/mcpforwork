import { DocsShell } from "@/components/docs/DocsShell";
import styles from "../docs.module.css";

export const metadata = { title: "MCP tools — mcpfor.work docs" };

const GROUPS: { area: string; id: string; tools: { name: string; what: string }[] }[] = [
  {
    area: "Profile",
    id: "profile",
    tools: [
      { name: "create_profile", what: "create a profile (constraints, target roles, label)" },
      { name: "get_profile", what: "read the active (or a given) profile" },
      { name: "update_profile", what: "patch constraints, roles, salary floor, work mode" },
      { name: "list_profiles", what: "list every profile with its active flag" },
      { name: "set_active_profile", what: "switch the profile all tools act on" },
      { name: "add_achievements", what: "append STAR achievements to the facts inventory" },
      { name: "set_style_profile", what: "tone, length, and voice for generated assets" },
      { name: "parse_cv", what: "extract candidate facts from pasted CV text — nothing is written until you confirm" },
      { name: "import_from_url_findings", what: "import profile facts you extracted from your LinkedIn/GitHub/portfolio" },
      { name: "profile_gaps", what: "what the profile cannot yet prove — gaps, never stuffed" },
    ],
  },
  {
    area: "Hunt",
    id: "hunt",
    tools: [
      { name: "hunt_plan", what: "the sources to search for this profile, with playbooks" },
      { name: "source_playbook", what: "one source's search URLs and pagination hints" },
      { name: "list_sources", what: "every pack source, filterable by country/sector" },
      { name: "submit_findings", what: "submit scraped postings for scoring and dedup" },
      { name: "check_seen", what: "the dedup gate — which URLs are already tracked" },
      { name: "report_playbook_result", what: "report a broken/changed source playbook" },
    ],
  },
  {
    area: "Review",
    id: "review",
    tools: [
      { name: "list_matches", what: "scored matches, filterable by score and status" },
      { name: "get_match", what: "one match with its full audit trail" },
      { name: "pipeline_stats", what: "counts per pipeline stage" },
      { name: "approve_match", what: "move a match to approved — ready to apply" },
      { name: "discard_match", what: "discard with an optional reason (reversible)" },
    ],
  },
  {
    area: "Generation",
    id: "generation",
    tools: [
      { name: "get_generation_brief", what: "the facts inventory + posting, ready to draft from" },
      { name: "submit_asset", what: "store a drafted CV/cover letter against a match" },
      { name: "get_assets", what: "list the assets generated for a match" },
      { name: "ats_coverage_check", what: "keyword coverage of an asset against the posting" },
      { name: "get_asset_file", what: "write a stored asset to a local file for form uploads" },
    ],
  },
  {
    area: "Apply",
    id: "apply",
    tools: [
      { name: "start_application", what: "preflight (dedup, caps, playbook) and open the loop" },
      { name: "report_apply_progress", what: "checkpoint where the form fill stands" },
      { name: "resolve_field", what: "map a form field to a profile fact — or a gap" },
      { name: "save_form_answer", what: "persist an answer for future applications" },
      { name: "abandon_application", what: "stop the loop, keeping the audit trail" },
      { name: "request_submit", what: "the only place a submit step exists — consent gate" },
      { name: "confirm_submitted", what: "record that a paused submit actually happened" },
      { name: "record_outcome", what: "interview, rejection, offer — close the loop" },
      { name: "record_application", what: "log an application you made outside the loop" },
    ],
  },
  {
    area: "Privacy & meta",
    id: "privacy",
    tools: [
      { name: "export_my_data", what: "everything stored about you, as JSON (GDPR export)" },
      {
        name: "delete_my_data",
        what: "two-step erasure: first a deletion summary + 5-min confirm token, then — only with that token — your account and all personal data are erased",
      },
      { name: "server_info", what: "version, transport, and the active tenant" },
    ],
  },
];

export default function McpToolsPage() {
  return (
    <DocsShell
      slug="/docs/mcp-tools"
      title="MCP tools"
      lead="The full tool surface your agent client gets over MCP — 38 tools, grouped by the phase of the job search they drive. The LLM is the client: every tool is a thin, audited step; the reasoning stays in your agent."
      toc={GROUPS.map((g) => ({ id: g.id, label: g.area }))}
    >
      {GROUPS.map((g) => (
        <section className={styles.section} id={g.id} key={g.id}>
          <h2 className={styles.h2}>
            {g.area} <span className={styles.inlineCode}>{g.tools.length}</span>
          </h2>
          <p className={styles.p}>
            {g.tools.map((t) => (
              <span key={t.name} style={{ display: "block", marginBottom: 6 }}>
                <code className={styles.inlineCode}>{t.name}</code> — {t.what}
              </span>
            ))}
          </p>
        </section>
      ))}
    </DocsShell>
  );
}
