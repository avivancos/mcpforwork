"""The MCP server's behavioral contract + next_action breadcrumbs.

DEPENDENCY-FREE by design: imports nothing from other layers, no I/O, no side
effects. `SERVER_INSTRUCTIONS` is the server-level prompt the client LLM reads;
`next_action(tool)` is the advisory next step attached to every tool response so
the client stays on-protocol mid-conversation.
"""

from __future__ import annotations

SERVER_INSTRUCTIONS = (
    "You are a supervised, sector- and country-agnostic job-search copilot. YOU "
    "(the client LLM) do all browsing in the user's own browser — the server "
    "never browses, fetches, scrapes, or calls an LLM. Never auto-submit: you "
    "draft, the human reviews and submits (the consent invariant).\n\n"
    "Default flow:\n"
    "1. /setup — build the profile (get_profile / update_profile / "
    "add_achievements / set_style_profile).\n"
    "2. /hunt — hunt_plan returns per-source search playbooks; open each in your "
    "browser, extract postings, submit_findings (deduped + scored), then "
    "list_matches to review.\n"
    "3. Review matches (assets + supervised apply arrive in later sprints).\n\n"
    "Always follow each response's next_action. Never claim anything the "
    "profile does not support."
)

# tool name -> advisory next step. Tools absent here get "" (see next_action).
_NEXT_ACTIONS: dict[str, str] = {
    "server_info": "Call get_profile to see the active profile, or run /setup to build it.",
    "create_profile": "Enrich it with update_profile / add_achievements, then run hunt_plan.",
    "get_profile": "Fill gaps with update_profile / add_achievements, then run hunt_plan.",
    "update_profile": "Add quantified wins with add_achievements, or run hunt_plan.",
    "list_profiles": "set_active_profile to switch, or get_profile to inspect one.",
    "set_active_profile": "get_profile to confirm the switch, then hunt_plan.",
    "add_achievements": "set_style_profile to capture the writing voice, or run hunt_plan.",
    "set_style_profile": "Run hunt_plan to start searching.",
    "import_from_url_findings": "get_profile to review the merged fields.",
    "profile_gaps": "Offer the FIRST gap conversationally; persist via update_profile.",
    "parse_cv": (
        "CONFIRM the extracted fields with the human (None = ask, never invent), "
        "then update_profile with the confirmed values + cv_text."
    ),
    "hunt_plan": "Open each search_url in YOUR browser, extract postings, then submit_findings.",
    "source_playbook": "Open the search_url in your browser and extract the postings.",
    "list_sources": "Run hunt_plan to pick sources for the active profile.",
    "submit_findings": "Call list_matches to review what scored well.",
    "check_seen": "Only browse/apply URLs marked 'new'; skip the rest.",
    "record_application": "Done — the posting will never re-surface. Back to /review.",
    "start_application": (
        "Execute the steps in the user's browser; report each with "
        "report_apply_progress. Unknown questions -> resolve_field. Never click Submit."
    ),
    "report_apply_progress": "Follow the returned next_step / repair / pause instruction.",
    "resolve_field": ("Use the answer as given; on ask_user, ask the human then save_form_answer."),
    "save_form_answer": "Answer saved — fill the field and continue the steps.",
    "request_submit": (
        "Show the human the filled form; THEY click Submit. Then confirm_submitted."
    ),
    "abandon_application": "Closed. start_application again to retry, or back to /review.",
    "export_my_data": "Your full data export. Save it somewhere safe.",
    "delete_my_data": "All your data is erased. Nothing was kept.",
    "confirm_submitted": "Recorded. Optionally record_outcome later; back to /review.",
    "record_outcome": "Noted for calibration. Back to /review or /hunt.",
    "get_asset_file": "Upload this file where the form asks for it.",
    "report_playbook_result": "Thanks — this feeds the next pack version. Back to /review.",
    "list_matches": "Run /review with the human: approve_match or discard_match each.",
    "approve_match": "Run /apply: get_generation_brief to draft materials.",
    "discard_match": "Back to list_matches for the next one.",
    "get_match": "Call get_generation_brief(finding_id, asset_type) to draft materials.",
    "get_generation_brief": (
        "Draft the asset honoring honesty_rules (only facts_inventory claims), then "
        "submit_asset and run ats_coverage_check."
    ),
    "submit_asset": "Run ats_coverage_check(finding_id, asset_id) to spot gaps.",
    "get_assets": "Iterate a draft with get_generation_brief, or run ats_coverage_check.",
    "ats_coverage_check": (
        "Add missing_but_have items truthfully; ACKNOWLEDGE genuine_gaps — never "
        "stuff keywords the facts_inventory cannot prove."
    ),
}


def next_action(tool_name: str) -> str:
    """The advisory next-step string for `tool_name` ("" if unmapped)."""
    return _NEXT_ACTIONS.get(tool_name, "")
