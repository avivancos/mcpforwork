"""abandon_application (S6.0): close an open session the human declines to
pursue so start_application can open a fresh one. Any open state -> abandoned
(machine-checked); submitted/verified are terminal and cannot be abandoned."""

import json

from mcpforwork.adapters.db import connect
from mcpforwork.adapters.db.backend import SqlUnitOfWork
from mcpforwork.entrypoints.mcp import server
from mcpforwork.services import apply as apply_service
from mcpforwork.services import hunt, profiles, review

_URL = "https://x.com/jobs/1"


def _approved(uow: SqlUnitOfWork, email: str = "u@example.com", url: str = _URL) -> tuple[int, int]:
    uid = uow.insert("INSERT INTO users (email) VALUES (?)", (email,))
    profiles.create_profile(
        uow,
        uid,
        {"full_name": "Ada", "contact_email": "a@x.com", "target_titles": ["Data Engineer"]},
    )
    hunt.submit_findings(uow, uid, "weworkremotely", [{"url": url, "title": "Data Engineer"}])
    fid = hunt.list_matches(uow, uid, min_score=0)[0]["id"]
    review.approve_match(uow, uid, fid)
    uow.commit()
    return uid, fid


def _walk_to(uow: SqlUnitOfWork, uid: int, app_id: int, session: dict) -> None:
    for step in session["steps"]:
        apply_service.report_apply_progress(uow, uid, app_id, step["step_id"], "ok")


def test_abandon_from_filling_marks_abandoned_and_audits(uow: SqlUnitOfWork) -> None:
    uid, fid = _approved(uow)
    app_id = apply_service.start_application(uow, uid, fid)["application_id"]  # filling
    result = apply_service.abandon_application(uow, uid, app_id, reason="changed my mind")
    uow.commit()
    assert result["ok"] is True
    assert result["state"] == "abandoned"
    assert (
        uow.fetchone("SELECT state FROM applications WHERE id = ?", (app_id,))["state"]
        == "abandoned"
    )
    audit = uow.fetchone(
        "SELECT detail FROM audit_log WHERE action = 'abandon_application' AND user_id = ?", (uid,)
    )
    assert "changed my mind" in audit["detail"]


def test_abandon_from_awaiting_human(uow: SqlUnitOfWork) -> None:
    uid, fid = _approved(uow)
    session = apply_service.start_application(uow, uid, fid)
    app_id = session["application_id"]
    _walk_to(uow, uid, app_id, session)  # -> awaiting_human
    uow.commit()
    assert apply_service.abandon_application(uow, uid, app_id)["ok"] is True
    # Read back — a silent no-op UPDATE (WHERE never matching) must not pass.
    assert (
        uow.fetchone("SELECT state FROM applications WHERE id = ?", (app_id,))["state"]
        == "abandoned"
    )


def test_abandon_from_submit_requested(uow: SqlUnitOfWork) -> None:
    uid, fid = _approved(uow)
    session = apply_service.start_application(uow, uid, fid)
    app_id = session["application_id"]
    _walk_to(uow, uid, app_id, session)
    apply_service.request_submit(uow, uid, app_id)  # -> submit_requested
    uow.commit()
    assert apply_service.abandon_application(uow, uid, app_id)["ok"] is True
    assert (
        uow.fetchone("SELECT state FROM applications WHERE id = ?", (app_id,))["state"]
        == "abandoned"
    )


def test_cannot_abandon_a_submitted_application(uow: SqlUnitOfWork) -> None:
    uid, fid = _approved(uow)
    session = apply_service.start_application(uow, uid, fid)
    app_id = session["application_id"]
    _walk_to(uow, uid, app_id, session)
    apply_service.request_submit(uow, uid, app_id)
    apply_service.confirm_submitted(uow, uid, app_id)  # -> submitted (terminal-ish)
    uow.commit()
    assert "error" in apply_service.abandon_application(uow, uid, app_id)
    assert (
        uow.fetchone("SELECT state FROM applications WHERE id = ?", (app_id,))["state"]
        == "submitted"  # unchanged
    )


def test_cannot_abandon_a_verified_application(uow: SqlUnitOfWork) -> None:
    # DoD names both terminal states. `verified` has no service transition yet,
    # so seed it directly on the real row (not a mock) and prove the machine
    # still refuses — the same can_transition guard that covers `submitted`.
    uid, fid = _approved(uow)
    session = apply_service.start_application(uow, uid, fid)
    app_id = session["application_id"]
    uow.execute("UPDATE applications SET state = 'verified' WHERE id = ?", (app_id,))
    uow.commit()
    assert "error" in apply_service.abandon_application(uow, uid, app_id)
    assert (
        uow.fetchone("SELECT state FROM applications WHERE id = ?", (app_id,))["state"]
        == "verified"  # unchanged
    )


def test_abandon_reason_defaults_to_empty(uow: SqlUnitOfWork) -> None:
    uid, fid = _approved(uow)
    app_id = apply_service.start_application(uow, uid, fid)["application_id"]
    assert apply_service.abandon_application(uow, uid, app_id)["ok"] is True  # no reason arg
    uow.commit()
    detail = uow.fetchone(
        "SELECT detail FROM audit_log WHERE action = 'abandon_application' AND user_id = ?", (uid,)
    )["detail"]
    assert json.loads(detail)["reason"] == ""


def test_foreign_or_unknown_application_is_rejected(uow: SqlUnitOfWork) -> None:
    uid, fid = _approved(uow)
    app_id = apply_service.start_application(uow, uid, fid)["application_id"]
    other = uow.insert("INSERT INTO users (email) VALUES (?)", ("b@example.com",))
    uow.commit()
    assert "error" in apply_service.abandon_application(uow, other, app_id)  # not their row
    assert "error" in apply_service.abandon_application(uow, uid, 9999)  # no such row
    # The foreign attempt left the row untouched.
    assert (
        uow.fetchone("SELECT state FROM applications WHERE id = ?", (app_id,))["state"] == "filling"
    )


def test_after_abandon_start_application_opens_a_fresh_session(uow: SqlUnitOfWork) -> None:
    uid, fid = _approved(uow)
    first = apply_service.start_application(uow, uid, fid)["application_id"]
    apply_service.abandon_application(uow, uid, first)
    uow.commit()
    reopened = apply_service.start_application(uow, uid, fid)
    uow.commit()
    assert reopened["application_id"] != first  # a NEW application, not the abandoned one
    assert reopened["state"] == "filling"
    assert not reopened.get("reopened")


def test_abandon_tool_persists_on_a_fresh_connection(mcp_env) -> None:
    server.update_profile(
        {"full_name": "Ada", "contact_email": "ada@x.com", "target_titles": ["Data Engineer"]}
    )
    server.submit_findings("weworkremotely", [{"url": _URL, "title": "Data Engineer"}])
    fid = json.loads(server.list_matches(0))["matches"][0]["id"]
    server.approve_match(fid)
    app_id = json.loads(server.start_application(fid))["application_id"]

    result = json.loads(server.abandon_application(app_id, "not interested"))
    assert result["ok"] is True

    fresh = connect(mcp_env)
    try:
        assert (
            fresh.fetchone("SELECT state FROM applications WHERE id = ?", (app_id,))["state"]
            == "abandoned"
        )
    finally:
        fresh.close()
    # unknown id through the tool returns an error envelope, not a crash
    assert "error" in json.loads(server.abandon_application(9999))


def test_abandon_application_is_a_registered_tool() -> None:
    import asyncio

    names = {t.name for t in asyncio.run(server.mcp.list_tools())}
    assert "abandon_application" in names
