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
from mcpforwork.services import audit, autopilot, hunt, profiles
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


def _authorize_l1(uow: UnitOfWork, user_id: int, app: dict[str, Any]) -> dict[str, Any]:
    """Turn a recorded L1 approval into a one-time authorization (S7.2a).

    The consent_level 0 → 1 flip is what makes the authorization exactly-once:
    a retried call re-reads consent_level 1 and re-returns the directive
    without writing a second authorization event."""
    instruction = (
        "The human approved THIS application's submit in the dashboard. Click "
        "Submit once, in the already-open form, then call "
        "confirm_submitted(application_id, evidence)."
    )
    if app["consent_level"] == 0:
        # Atomic flip: the WHERE clause makes exactly-once hold even under
        # concurrent request_submit transactions — the loser matches 0 rows
        # and must not write a second authorization event.
        cur = uow.execute(
            "UPDATE applications SET consent_level = 1, updated_at = ?"
            " WHERE id = ? AND user_id = ? AND consent_level = 0",
            (utcnow_iso(), app["id"], user_id),
        )
        if cur.rowcount == 1:
            audit.record(
                uow,
                user_id,
                "submit_authorized",
                {
                    "application_id": app["id"],
                    "level": 1,
                    "approved_at": app["submit_approved_at"],
                    "approved_via": app["submit_approved_via"],
                },
            )
    return {
        "decision": "submit_authorized",
        "instruction": instruction,
        "application_id": app["id"],
    }


def _l2_authorized_today(uow: UnitOfWork, user_id: int, now: datetime) -> int:
    """L2 authorizations minted in the current UTC calendar day — the cap
    window (ADR 0001 follow-up: the day boundary is UTC, load-bearing here).
    Counted from the audit log's immutable created_at; the level-2 marker in
    the JSON detail is a pre-filter both dialects evaluate as text."""
    day = now.strftime("%Y-%m-%d")
    row = uow.fetchone(
        "SELECT COUNT(*) AS n FROM audit_log WHERE user_id = ?"
        " AND action = 'submit_authorized' AND created_at >= ? AND detail LIKE ?",
        (user_id, day, '%"level": 2%'),
    )
    return row["n"]


def _authorize_l2(
    uow: UnitOfWork, user_id: int, app: dict[str, Any], snapshot: dict[str, Any]
) -> dict[str, Any]:
    """Turn an active L2 policy into a one-time authorization (S7.2b).

    Same exactly-once pattern as L1: the consent_level 0 → 2 flip is atomic,
    and only the transaction that wins the flip writes the criteria-snapshot
    audit row. Re-entry (consent_level already 2) re-returns the directive."""
    instruction = (
        "Your recorded autopilot policy authorizes THIS application's submit "
        "(the criteria snapshot is in the audit log). Click Submit once, in the "
        "already-open form, then call confirm_submitted(application_id, evidence)."
    )
    if app["consent_level"] == 0:
        cur = uow.execute(
            "UPDATE applications SET consent_level = 2, updated_at = ?"
            " WHERE id = ? AND user_id = ? AND consent_level = 0",
            (utcnow_iso(), app["id"], user_id),
        )
        if cur.rowcount == 1:
            audit.record(
                uow,
                user_id,
                "submit_authorized",
                {"application_id": app["id"], "level": 2, "snapshot": snapshot},
            )
    return {
        "decision": "submit_authorized",
        "instruction": instruction,
        "application_id": app["id"],
    }


def request_submit(
    uow: UnitOfWork,
    user_id: int,
    application_id: int,
    summary: str = "",
    *,
    now: datetime | None = None,
    safe_sources: frozenset[str] | set[str] | None = None,
) -> dict[str, Any]:
    """THE consent gate — the only path toward submission.

    Without a recorded consent artifact the decision is ALWAYS `await_human`:
    the client shows the filled form; the human clicks Submit themselves, then
    the client calls confirm_submitted. L1 (S7.2a, ADR 0005): an approval
    recorded through the human-session API turns a re-entry into a one-time
    `submit_authorized`. L2 (S7.2b): an active policy authorizes submits on
    auto_apply_safe sources at/above its min score, up to its UTC daily cap.
    The MCP entrypoint can never write either artifact."""
    app = _load_application(uow, user_id, application_id)
    if app is None:
        return {"error": f"application {application_id} not found"}
    reentry = app["state"] == "submit_requested"
    if not reentry and not can_transition(app["state"], "submit_requested"):
        return {"error": f"application is '{app['state']}' — finish the steps first"}
    if not reentry:
        uow.execute(
            "UPDATE applications SET state = 'submit_requested', updated_at = ?"
            " WHERE id = ? AND user_id = ?",
            (utcnow_iso(), application_id, user_id),
        )
    if app["submit_approved_at"] is not None:
        return _authorize_l1(uow, user_id, app)
    if app["consent_level"] == 2:
        # Already L2-authorized: re-entry re-returns the directive without a
        # cap re-check — a minted authorization is never stranded mid-submit.
        return _authorize_l2(uow, user_id, app, snapshot={})

    policy = autopilot.get_policy(uow, user_id)
    refusal = ""
    if policy is not None:
        # Serialize L2 authorization per user (S7.2d): the cap count and the
        # consent flip must be atomic ACROSS transactions — otherwise N
        # parallel request_submit calls on distinct pre-staged applications
        # each read authorized_today < cap and all flip (TOCTOU). This no-op
        # self-update takes the user's row write lock: on SQLite it grabs the
        # database-wide writer lock, on Postgres a row lock after which READ
        # COMMITTED re-snapshots the count. Concurrent L2 calls for one user
        # thus run one-at-a-time; different users never block each other.
        uow.execute("UPDATE users SET id = id WHERE id = ?", (user_id,))
        match = hunt.get_match(uow, user_id, app["finding_id"])
        safe = safe_sources if safe_sources is not None else autopilot.safe_source_slugs()
        decision = autopilot.evaluate(
            policy=policy,
            score=(match["score"] or 0) if match else 0,
            source_slug=match["source_slug"] if match else "",
            safe_sources=safe,
            authorized_today=_l2_authorized_today(uow, user_id, now or datetime.now(UTC)),
        )
        if decision["authorize"]:
            return _authorize_l2(uow, user_id, app, decision["snapshot"])
        refusal = f" Autopilot policy did not authorize it ({decision['reason']})."

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
        "reason": refusal.strip(),
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
        # Autopilot-authorized submits are distinguished in the record (S7.2).
        channel={0: "browser_supervised", 1: "browser_autopilot_l1", 2: "browser_autopilot_l2"}[
            app["consent_level"]
        ],
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
        return {"error": f"outcome must be one of {sorted(OUTCOMES)}", "kind": "invalid_input"}
    app = _load_application(uow, user_id, application_id)
    if app is None:
        return {"error": f"application {application_id} not found", "kind": "not_found"}
    if app["state"] not in ("submitted", "verified"):
        return {
            "error": f"application is '{app['state']}' — outcomes apply after submission",
            "kind": "invalid_state",
        }
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
