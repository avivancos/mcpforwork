"""request_submit consent gate + confirm_submitted + outcomes (S4.3, evolved S7.2a).

THE invariant: without a recorded consent artifact, request_submit ALWAYS
awaits the human. Consent artifacts are written exclusively by the
human-session HTTP API (services/autopilot.py), never by the MCP entrypoint
(ADR 0005). L1: a dashboard approval authorizes one submit, once.
"""

import inspect
from pathlib import Path

from mcpforwork import config
from mcpforwork.adapters.db.backend import SqlUnitOfWork
from mcpforwork.services import apply as apply_service
from mcpforwork.services import assets, dedup, hunt, profiles, review

_URL = "https://x.com/jobs/1"


def _ready_app(uow: SqlUnitOfWork) -> tuple[int, int, int]:
    uid = uow.insert("INSERT INTO users (email) VALUES (?)", ("u@example.com",))
    profiles.create_profile(
        uow,
        uid,
        {"full_name": "Ada", "contact_email": "a@x.com", "target_titles": ["Data Engineer"]},
    )
    hunt.submit_findings(uow, uid, "weworkremotely", [{"url": _URL, "title": "Data Engineer"}])
    fid = hunt.list_matches(uow, uid, min_score=0)[0]["id"]
    review.approve_match(uow, uid, fid)
    session = apply_service.start_application(uow, uid, fid)
    app_id = session["application_id"]
    for step in session["steps"]:
        apply_service.report_apply_progress(uow, uid, app_id, step["step_id"], "ok")
    uow.commit()
    return uid, fid, app_id


def test_request_submit_at_l0_always_awaits_the_human(uow: SqlUnitOfWork) -> None:
    uid, _, app_id = _ready_app(uow)
    result = apply_service.request_submit(uow, uid, app_id, summary="filled form shown")
    uow.commit()
    assert result["decision"] == "await_human"
    assert "submit_authorized" not in str(result)
    audit = uow.fetchone(
        "SELECT detail FROM audit_log WHERE action = 'request_submit' AND user_id = ?", (uid,)
    )
    assert "filled form shown" in audit["detail"]


def test_no_approval_means_every_path_awaits_the_human(uow: SqlUnitOfWork) -> None:
    # L0 default (S7.2a): without a recorded approval, request_submit awaits
    # the human on first entry AND on every re-entry in submit_requested.
    uid, _, app_id = _ready_app(uow)
    first = apply_service.request_submit(uow, uid, app_id, summary="filled form shown")
    reentry = apply_service.request_submit(uow, uid, app_id)
    uow.commit()
    assert first["decision"] == "await_human"
    assert reentry["decision"] == "await_human"


def test_approval_write_sql_lives_only_in_the_autopilot_service() -> None:
    # ADR 0005: the consent artifact (submit_approved_at) is written exclusively
    # by services/autopilot.py — the human-session API's service. Any other
    # module containing the write statement is a consent-gate violation.
    import mcpforwork.services.autopilot as autopilot_service

    allowed = Path(inspect.getsourcefile(autopilot_service) or "")
    src_root = Path(__file__).parent.parent / "src" / "mcpforwork"
    offenders = [
        p
        for p in src_root.rglob("*.py")
        if p != allowed
        and "adapters/db" not in str(p)  # schema/migrations define the columns
        and "SET submit_approved_at" in p.read_text()
    ]
    assert offenders == []


def test_mcp_entrypoint_never_references_the_approval_write() -> None:
    # ADR 0005: no MCP tool call sequence (possibly prompt-injected by posting
    # content) may mint consent — the entrypoint must not reference the write.
    from mcpforwork.entrypoints.mcp import server

    source = inspect.getsource(server)
    assert "approve_submit" not in source
    assert "submit_approved_at" not in source


def test_request_submit_requires_awaiting_human_state(uow: SqlUnitOfWork) -> None:
    uid = uow.insert("INSERT INTO users (email) VALUES (?)", ("v@example.com",))
    profiles.create_profile(uow, uid, {"target_titles": ["Data Engineer"]})
    hunt.submit_findings(uow, uid, "weworkremotely", [{"url": "https://y.com/2", "title": "DE"}])
    fid = hunt.list_matches(uow, uid, min_score=0)[0]["id"]
    review.approve_match(uow, uid, fid)
    app_id = apply_service.start_application(uow, uid, fid)["application_id"]  # still filling
    uow.commit()
    assert "error" in apply_service.request_submit(uow, uid, app_id)


def test_confirm_submitted_flips_state_and_records_the_application(uow: SqlUnitOfWork) -> None:
    uid, fid, app_id = _ready_app(uow)
    apply_service.request_submit(uow, uid, app_id)
    result = apply_service.confirm_submitted(uow, uid, app_id, evidence="confirmation page seen")
    uow.commit()
    assert result["state"] == "submitted"
    # The dedup gate now knows the URL…
    item = dedup.check_seen(uow, uid, [_URL])["items"][0]
    assert item["applied"] is True
    # …the finding is terminal, and evidence is stored.
    row = uow.fetchone("SELECT state, evidence FROM applications WHERE id = ?", (app_id,))
    assert row["state"] == "submitted"
    assert "confirmation" in row["evidence"]


def test_confirm_without_await_state_errors(uow: SqlUnitOfWork) -> None:
    uid = uow.insert("INSERT INTO users (email) VALUES (?)", ("w@example.com",))
    profiles.create_profile(uow, uid, {"target_titles": ["DE"]})
    hunt.submit_findings(uow, uid, "weworkremotely", [{"url": "https://z.com/3", "title": "DE"}])
    fid = hunt.list_matches(uow, uid, min_score=0)[0]["id"]
    review.approve_match(uow, uid, fid)
    app_id = apply_service.start_application(uow, uid, fid)["application_id"]
    uow.commit()
    assert "error" in apply_service.confirm_submitted(uow, uid, app_id)


def test_submitted_application_cannot_regress_to_awaiting_human(uow: SqlUnitOfWork) -> None:
    # Gate P1 regression: re-reporting the last step ok after submission must be
    # rejected — the machine forbids submitted -> awaiting_human.
    uid, _, app_id = _ready_app(uow)
    apply_service.request_submit(uow, uid, app_id)
    apply_service.confirm_submitted(uow, uid, app_id)
    uow.commit()
    last_step = apply_service._load_application(uow, uid, app_id)["steps"][-1]
    result = apply_service.report_apply_progress(uow, uid, app_id, last_step["step_id"], "ok")
    assert "error" in result
    state = uow.fetchone("SELECT state FROM applications WHERE id = ?", (app_id,))["state"]
    assert state == "submitted"  # unchanged


def test_confirm_without_request_submit_is_rejected(uow: SqlUnitOfWork) -> None:
    # The audit trail must always carry request_submit before confirm_submitted.
    uid, _, app_id = _ready_app(uow)  # awaiting_human, but no request yet
    assert "error" in apply_service.confirm_submitted(uow, uid, app_id)


def test_double_confirm_is_rejected(uow: SqlUnitOfWork) -> None:
    uid, _, app_id = _ready_app(uow)
    apply_service.request_submit(uow, uid, app_id)
    apply_service.confirm_submitted(uow, uid, app_id)
    assert "error" in apply_service.confirm_submitted(uow, uid, app_id)


def test_outcome_before_submission_is_rejected(uow: SqlUnitOfWork) -> None:
    uid, _, app_id = _ready_app(uow)  # awaiting_human, not submitted
    assert "error" in apply_service.record_outcome(uow, uid, app_id, "interview")


def test_record_outcome_persists_and_validates(uow: SqlUnitOfWork) -> None:
    uid, _, app_id = _ready_app(uow)
    apply_service.request_submit(uow, uid, app_id)
    apply_service.confirm_submitted(uow, uid, app_id)
    assert "error" in apply_service.record_outcome(uow, uid, app_id, "ghosted-ish")
    result = apply_service.record_outcome(uow, uid, app_id, "interview", notes="phone screen")
    uow.commit()
    assert result["ok"] is True
    assert (
        uow.fetchone("SELECT outcome FROM applications WHERE id = ?", (app_id,))["outcome"]
        == "interview"
    )


def test_get_asset_file_writes_under_data_dir(
    uow: SqlUnitOfWork, tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("MCPFORWORK_DATA_DIR", str(tmp_path / "data"))
    uid, fid, _ = _ready_app(uow)
    aid = assets.submit_asset(uow, uid, fid, "cv", "# Ada CV")["asset_id"]
    uow.commit()
    result = apply_service.get_asset_file(uow, uid, aid)
    path = Path(result["path"])
    assert path.is_file()
    assert path.read_text() == "# Ada CV"
    assert str(config.data_dir()) in str(path)
    # foreign asset rejected
    other = uow.insert("INSERT INTO users (email) VALUES (?)", ("b@example.com",))
    assert "error" in apply_service.get_asset_file(uow, other, aid)
