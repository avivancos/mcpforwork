"""Browser-apply orchestration: the server choreographs, the client's browser acts.

start_application runs the deterministic preflight and persists the session.
Consent is structural: the step plan never contains a submit step; only
request_submit (S4.3) routes submission, and at L0 it always awaits the human.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from mcpforwork import config
from mcpforwork.domain.apply_flow import build_steps, can_transition
from mcpforwork.domain.dedup import dedup_hash
from mcpforwork.packs import registry
from mcpforwork.ports.db import UnitOfWork
from mcpforwork.services import assets as assets_service
from mcpforwork.services import audit, hunt, profiles
from mcpforwork.services import dedup as dedup_service
from mcpforwork.services.briefs import ASSET_TYPES
from mcpforwork.services.clock import utcnow_iso

MAX_APPLICATIONS_PER_DAY = 10

_OPEN_STATES = ("draft", "filling", "awaiting_human", "submit_requested")

_OBSTACLES = frozenset({"captcha", "login", "2fa", "hostile_bot_check"})

# Normalized form labels that unambiguously ask about the CANDIDATE, mapped to
# the profile field that answers them. Anything else goes to saved form_answers
# or ask_user — a greedy token match ("Company name" ~ name) invented answers.
_CANDIDATE_LABELS = {
    "name": "full_name",
    "your name": "full_name",
    "full name": "full_name",
    "first and last name": "full_name",
    "email": "contact_email",
    "e-mail": "contact_email",
    "email address": "contact_email",
    "your email": "contact_email",
    "city": "city",
    "your city": "city",
    "country": "country",
    "your country": "country",
}


def _today_started_count(uow: UnitOfWork, user_id: int) -> int:
    day = datetime.now(UTC).strftime("%Y-%m-%d")
    row = uow.fetchone(
        "SELECT COUNT(*) AS n FROM applications WHERE user_id = ? AND created_at >= ?",
        (user_id, day),
    )
    return row["n"]


def start_application(uow: UnitOfWork, user_id: int, finding_id: int) -> dict[str, Any]:
    """Deterministic preflight → persisted application session with a step plan."""
    match = hunt.get_match(uow, user_id, finding_id)
    if match is None:
        return {"error": f"match {finding_id} not found"}
    if match["status"] != "approved":
        return {"error": f"match {finding_id} is '{match['status']}' — approve it first (/review)"}

    # Idempotent re-open: one open application per finding.
    placeholders = ", ".join(["?"] * len(_OPEN_STATES))
    open_row = uow.fetchone(
        f"SELECT id, state, steps, consent_level FROM applications"
        f" WHERE user_id = ? AND finding_id = ? AND state IN ({placeholders})",
        (user_id, finding_id, *_OPEN_STATES),
    )
    if open_row is not None:
        return {
            "application_id": open_row["id"],
            "state": open_row["state"],
            "consent_level": open_row["consent_level"],
            "steps": json.loads(open_row["steps"] or "[]"),
            "reopened": True,
        }

    # Dedup gate: never apply twice.
    digest = dedup_hash(match["url"])
    if uow.fetchone(
        "SELECT id FROM external_applications WHERE dedup_hash = ? AND user_id = ?",
        (digest, user_id),
    ):
        return {"error": "already applied to this posting (dedup gate)"}

    # Daily cap protects application quality and the user's reputation.
    if _today_started_count(uow, user_id) >= MAX_APPLICATIONS_PER_DAY:
        return {"error": f"daily cap reached ({MAX_APPLICATIONS_PER_DAY}/day)"}

    profile = profiles.get_profile(uow, user_id)
    if profile is None:
        return {"error": "no active profile — run /setup first"}
    asset_rows = assets_service.get_assets(uow, user_id, finding_id)
    playbook = registry.load_sources().get(match["source_slug"])
    apply_playbook = playbook.apply if playbook else {}

    steps = build_steps(match, profile, asset_rows, apply_playbook)
    app_id = uow.insert(
        "INSERT INTO applications (user_id, finding_id, state, apply_method, steps)"
        " VALUES (?, ?, 'filling', ?, ?)",
        (user_id, finding_id, apply_playbook.get("ats_hint"), json.dumps(steps)),
    )
    audit.record(
        uow, user_id, "start_application", {"application_id": app_id, "finding_id": finding_id}
    )
    return {
        "application_id": app_id,
        "state": "filling",
        "consent_level": 0,
        "steps": steps,
        "warnings": []
        if asset_rows
        else ["no drafted assets for this match — consider /apply first"],
    }


def _load_application(uow: UnitOfWork, user_id: int, application_id: int) -> dict[str, Any] | None:
    row = uow.fetchone(
        "SELECT * FROM applications WHERE id = ? AND user_id = ?", (application_id, user_id)
    )
    if row is None:
        return None
    row = dict(row)
    row["steps"] = json.loads(row["steps"] or "[]")
    return row


def report_apply_progress(
    uow: UnitOfWork,
    user_id: int,
    application_id: int,
    step_id: int,
    status: str,
    observed: str = "",
    obstacle: str = "",
) -> dict[str, Any]:
    """The heartbeat of the apply loop: the client reports each step; the server
    answers with the next step, a repair, or a human-pause. Never a submit."""
    app = _load_application(uow, user_id, application_id)
    if app is None:
        return {"error": f"application {application_id} not found"}
    if app["state"] != "filling":
        # The state machine is enforced here: once the plan is exhausted (or the
        # application left the filling state) no report can move it — a
        # submitted application can never regress to awaiting_human.
        return {"error": f"application is '{app['state']}' — reports only apply while filling"}
    if status not in ("ok", "blocked", "mismatch"):
        return {"error": "status must be ok | blocked | mismatch"}
    steps = app["steps"]
    current = next((s for s in steps if s["step_id"] == step_id), None)
    if current is None:
        return {"error": f"unknown step {step_id}"}

    audit.record(
        uow,
        user_id,
        "report_apply_progress",
        {
            "application_id": application_id,
            "step_id": step_id,
            "status": status,
            "obstacle": obstacle or None,
        },
    )

    if status == "mismatch":
        return {
            "state": app["state"],
            "retry_step": current,
            "repair": (
                "The page diverged from the plan. Re-read the form, adapt to what is "
                "actually on screen, and retry this step. Observed: " + (observed or "n/a")
            ),
        }

    if status == "blocked":
        kind = obstacle if obstacle in _OBSTACLES else "unknown"
        return {
            "state": app["state"],
            "pause": True,
            "obstacle": kind,
            "instruction": (
                "Pause. Ask the HUMAN to resolve the "
                f"{kind} in their own browser (they are present — it is their session); "
                "captchas and logins are always human-solved. When they confirm, call "
                "report_apply_progress(status='ok') for this step to resume."
            ),
        }

    # status == ok — advance past this step.
    idx = steps.index(current)
    uow.execute(
        "UPDATE applications SET current_step = ?, updated_at = ? WHERE id = ? AND user_id = ?",
        (current["step_id"], utcnow_iso(), application_id, user_id),
    )
    if idx + 1 < len(steps):
        return {"state": app["state"], "next_step": steps[idx + 1]}
    # Plan exhausted: the form is filled and reviewed — the human decides next.
    assert can_transition(app["state"], "awaiting_human")  # machine-checked write
    uow.execute(
        "UPDATE applications SET state = 'awaiting_human', updated_at = ?"
        " WHERE id = ? AND user_id = ?",
        (utcnow_iso(), application_id, user_id),
    )
    return {
        "state": "awaiting_human",
        "next_action": (
            "All steps done. Call request_submit(application_id) — the human reviews "
            "and decides; you never click Submit."
        ),
    }


def abandon_application(
    uow: UnitOfWork, user_id: int, application_id: int, reason: str = ""
) -> dict[str, Any]:
    """Close an open session the human decided not to pursue (any open state ->
    abandoned). Submitted/verified are terminal — the machine rejects those. A
    later start_application for the same finding then opens a fresh session,
    because `abandoned` is not an open state."""
    app = _load_application(uow, user_id, application_id)
    if app is None:
        return {"error": f"application {application_id} not found"}
    if not can_transition(app["state"], "abandoned"):
        return {"error": f"application is '{app['state']}' — cannot abandon"}
    uow.execute(
        "UPDATE applications SET state = 'abandoned', updated_at = ? WHERE id = ? AND user_id = ?",
        (utcnow_iso(), application_id, user_id),
    )
    audit.record(
        uow, user_id, "abandon_application", {"application_id": application_id, "reason": reason}
    )
    return {"ok": True, "state": "abandoned", "application_id": application_id}


def resolve_field(
    uow: UnitOfWork,
    user_id: int,
    application_id: int,
    field_label: str,
    field_type: str = "",
    options: list[str] | None = None,
) -> dict[str, Any]:
    """Deterministic answer for a screener question the plan didn't predict:
    profile fields first, then saved form_answers; otherwise ask the human."""
    app = _load_application(uow, user_id, application_id)
    if app is None:
        return {"error": f"application {application_id} not found"}
    profile = profiles.get_profile(uow, user_id)
    if profile is None:
        return {"error": "no active profile"}

    # 1) A human-confirmed saved answer always wins (exact label match).
    answers: dict[str, str] = json.loads(profile.get("form_answers") or "{}")
    for saved_label, saved_answer in answers.items():
        if saved_label.lower() == field_label.lower():
            return {"field_label": field_label, "answer": saved_answer, "source": "form_answers"}

    # 2) Profile fields only for labels that UNAMBIGUOUSLY ask about the
    #    candidate (strict allowlist — "Company name" / "Hiring manager name"
    #    must NEVER be answered with the candidate's own data).
    normalized = " ".join(field_label.lower().replace("*", " ").split())
    if profile.get(_CANDIDATE_LABELS.get(normalized, "")):
        field = _CANDIDATE_LABELS[normalized]
        return {"field_label": field_label, "answer": profile[field], "source": field}

    return {
        "field_label": field_label,
        "ask_user": True,
        "instruction": (
            "Ask the human for this answer, then persist it with save_form_answer so "
            "it is never asked twice. Never invent an answer."
        ),
        "options": options or [],
    }


OUTCOMES = frozenset({"no_reply", "rejected", "interview", "offer", "hired"})


def request_submit(
    uow: UnitOfWork, user_id: int, application_id: int, summary: str = ""
) -> dict[str, Any]:
    """THE consent gate — the only path toward submission.

    Consent level 0 (the only level until the S7 autopilot card): the decision
    is ALWAYS `await_human`. The client shows the filled form; the human clicks
    Submit themselves, then the client calls confirm_submitted."""
    app = _load_application(uow, user_id, application_id)
    if app is None:
        return {"error": f"application {application_id} not found"}
    if not can_transition(app["state"], "submit_requested"):
        return {"error": f"application is '{app['state']}' — finish the steps first"}
    uow.execute(
        "UPDATE applications SET state = 'submit_requested', updated_at = ?"
        " WHERE id = ? AND user_id = ?",
        (utcnow_iso(), application_id, user_id),
    )
    audit.record(
        uow,
        user_id,
        "request_submit",
        {
            "application_id": application_id,
            "summary": summary,
            "consent_level": app["consent_level"],
        },
    )
    return {
        "decision": "await_human",
        "instruction": (
            "Show the human the filled form now. THE HUMAN clicks Submit in their "
            "browser. After they confirm it went through, call "
            "confirm_submitted(application_id, evidence)."
        ),
        "application_id": application_id,
    }


def confirm_submitted(
    uow: UnitOfWork, user_id: int, application_id: int, evidence: str = ""
) -> dict[str, Any]:
    """The human confirmed they submitted: close the loop — state, dedup record,
    finding flip, audit trail."""
    app = _load_application(uow, user_id, application_id)
    if app is None:
        return {"error": f"application {application_id} not found"}
    if not can_transition(app["state"], "submitted"):
        return {"error": f"application is '{app['state']}' — request_submit first"}
    match = hunt.get_match(uow, user_id, app["finding_id"])
    uow.execute(
        "UPDATE applications SET state = 'submitted', evidence = ?, updated_at = ?"
        " WHERE id = ? AND user_id = ?",
        (evidence or None, utcnow_iso(), application_id, user_id),
    )
    recorded = dedup_service.record_application(
        uow,
        user_id,
        url=match["url"],
        channel="browser_supervised",
        title=match.get("title") or "",
        company_name=match.get("company_name") or "",
        finding_id=app["finding_id"],
        notes=f"application {application_id}",
    )
    audit.record(
        uow,
        user_id,
        "confirm_submitted",
        {"application_id": application_id, "evidence": bool(evidence)},
    )
    return {
        "ok": True,
        "state": "submitted",
        "application_id": application_id,
        "external_application_id": recorded.get("external_application_id"),
    }


def record_outcome(
    uow: UnitOfWork, user_id: int, application_id: int, outcome: str, notes: str = ""
) -> dict[str, Any]:
    """Store what actually happened — the calibration loop's raw data."""
    if outcome not in OUTCOMES:
        return {"error": f"outcome must be one of {sorted(OUTCOMES)}"}
    app = _load_application(uow, user_id, application_id)
    if app is None:
        return {"error": f"application {application_id} not found"}
    if app["state"] not in ("submitted", "verified"):
        return {"error": f"application is '{app['state']}' — outcomes apply after submission"}
    uow.execute(
        "UPDATE applications SET outcome = ?, updated_at = ? WHERE id = ? AND user_id = ?",
        (outcome, utcnow_iso(), application_id, user_id),
    )
    audit.record(
        uow,
        user_id,
        "record_outcome",
        {"application_id": application_id, "outcome": outcome, "notes": notes},
    )
    return {"ok": True, "application_id": application_id, "outcome": outcome}


def get_asset_file(uow: UnitOfWork, user_id: int, asset_id: int) -> dict[str, Any]:
    """Write the asset to a local file for form uploads (self-host path; hosted
    signed URLs arrive with the hosted sprint)."""
    row = uow.fetchone(
        "SELECT id, asset_type, content FROM generated_assets WHERE id = ? AND user_id = ?",
        (asset_id, user_id),
    )
    if row is None:
        return {"error": f"asset {asset_id} not found"}
    if row["asset_type"] not in ASSET_TYPES:  # read-side whitelist (defense in depth)
        return {"error": f"unexpected asset_type {row['asset_type']!r}"}
    directory = config.data_dir() / "assets"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{row['id']}_{row['asset_type']}.md"
    path.write_text(row["content"], encoding="utf-8")
    return {"ok": True, "path": str(path), "asset_type": row["asset_type"]}


def save_form_answer(
    uow: UnitOfWork, user_id: int, field_label: str, answer: str
) -> dict[str, Any]:
    """Persist a human-confirmed screener answer to the profile (progressive)."""
    profile = profiles.get_profile(uow, user_id)
    if profile is None:
        return {"error": "no active profile"}
    answers: dict[str, str] = json.loads(profile.get("form_answers") or "{}")
    answers[field_label] = answer
    uow.execute(
        "UPDATE profiles SET form_answers = ? WHERE id = ? AND user_id = ?",
        (json.dumps(answers), profile["id"], user_id),
    )
    audit.record(uow, user_id, "save_form_answer", {"field_label": field_label})
    return {"ok": True, "saved": field_label}
