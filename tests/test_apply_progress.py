"""report_apply_progress loop + resolve_field progressive profiling (S4.2)."""

from mcpforwork.adapters.db.backend import SqlUnitOfWork
from mcpforwork.services import apply as apply_service
from mcpforwork.services import hunt, profiles, review


def _session(uow: SqlUnitOfWork) -> tuple[int, int, dict]:
    uid = uow.insert("INSERT INTO users (email) VALUES (?)", ("u@example.com",))
    profiles.create_profile(
        uow,
        uid,
        {"full_name": "Ada", "contact_email": "ada@x.com", "target_titles": ["Data Engineer"]},
    )
    hunt.submit_findings(
        uow, uid, "weworkremotely", [{"url": "https://x.com/1", "title": "Data Engineer"}]
    )
    fid = hunt.list_matches(uow, uid, min_score=0)[0]["id"]
    review.approve_match(uow, uid, fid)
    session = apply_service.start_application(uow, uid, fid)
    uow.commit()
    return uid, session["application_id"], session


def test_ok_advances_to_the_next_step(uow: SqlUnitOfWork) -> None:
    uid, app_id, session = _session(uow)
    first = session["steps"][0]
    result = apply_service.report_apply_progress(uow, uid, app_id, first["step_id"], "ok")
    uow.commit()
    assert result["next_step"]["step_id"] == first["step_id"] + 1
    assert result["state"] == "filling"


def test_last_ok_reaches_awaiting_human_never_submit(uow: SqlUnitOfWork) -> None:
    uid, app_id, session = _session(uow)
    result: dict = {}
    for step in session["steps"]:
        result = apply_service.report_apply_progress(uow, uid, app_id, step["step_id"], "ok")
    uow.commit()
    assert result["state"] == "awaiting_human"
    assert "request_submit" in result["next_action"]
    assert "submit_authorized" not in str(result)
    row = uow.fetchone("SELECT state FROM applications WHERE id = ?", (app_id,))
    assert row["state"] == "awaiting_human"


def test_mismatch_keeps_the_step_and_returns_a_repair(uow: SqlUnitOfWork) -> None:
    uid, app_id, session = _session(uow)
    first = session["steps"][0]
    result = apply_service.report_apply_progress(
        uow, uid, app_id, first["step_id"], "mismatch", observed="selector gone"
    )
    assert result["repair"]
    assert result["retry_step"]["step_id"] == first["step_id"]


def test_blocked_with_obstacle_pauses_for_the_human(uow: SqlUnitOfWork) -> None:
    uid, app_id, session = _session(uow)
    result = apply_service.report_apply_progress(
        uow, uid, app_id, session["steps"][0]["step_id"], "blocked", obstacle="captcha"
    )
    uow.commit()
    assert result["pause"] is True
    assert "human" in result["instruction"].lower()
    # never bypassed: the instruction must not suggest solving it automatically
    assert "bypass" not in result["instruction"].lower()


def test_out_of_order_or_foreign_reports_rejected(uow: SqlUnitOfWork) -> None:
    uid, app_id, session = _session(uow)
    assert "error" in apply_service.report_apply_progress(uow, uid, app_id, 99, "ok")
    other = uow.insert("INSERT INTO users (email) VALUES (?)", ("b@example.com",))
    assert "error" in apply_service.report_apply_progress(
        uow, other, app_id, session["steps"][0]["step_id"], "ok"
    )
    assert "error" in apply_service.report_apply_progress(
        uow, uid, app_id, session["steps"][0]["step_id"], "sideways"
    )


def test_resolve_field_never_answers_third_party_labels(uow: SqlUnitOfWork) -> None:
    # Gate P1 regression: "Company name" / "Hiring manager name" must NOT be
    # answered with the candidate's own data — never invent.
    uid, app_id, _ = _session(uow)
    for label in (
        "Company name",
        "Hiring manager name",
        "Referral email (if any)",
        "Name of your current employer",
    ):
        result = apply_service.resolve_field(uow, uid, app_id, label)
        assert result.get("ask_user") is True, label


def test_saved_answer_overrides_the_label_heuristic(uow: SqlUnitOfWork) -> None:
    # A human-confirmed answer must win even for a label the heuristic matches.
    uid, app_id, _ = _session(uow)
    apply_service.save_form_answer(uow, uid, "Email", "work-alias@x.com")
    uow.commit()
    assert apply_service.resolve_field(uow, uid, app_id, "Email")["answer"] == "work-alias@x.com"


def test_every_progress_report_is_audited(uow: SqlUnitOfWork) -> None:
    uid, app_id, session = _session(uow)
    apply_service.report_apply_progress(uow, uid, app_id, session["steps"][0]["step_id"], "ok")
    uow.commit()
    rows = uow.fetchall(
        "SELECT detail FROM audit_log WHERE user_id = ? AND action = 'report_apply_progress'",
        (uid,),
    )
    assert len(rows) == 1


def test_resolve_field_answers_from_profile(uow: SqlUnitOfWork) -> None:
    uid, app_id, _ = _session(uow)
    result = apply_service.resolve_field(uow, uid, app_id, "Email address")
    assert result["answer"] == "ada@x.com"
    assert result.get("ask_user") is not True


def test_resolve_field_unknown_asks_the_user_then_saved_answer_is_reused(
    uow: SqlUnitOfWork,
) -> None:
    uid, app_id, _ = _session(uow)
    first = apply_service.resolve_field(uow, uid, app_id, "Notice period")
    assert first["ask_user"] is True

    apply_service.save_form_answer(uow, uid, "Notice period", "1 month")
    uow.commit()
    second = apply_service.resolve_field(uow, uid, app_id, "Notice period")
    assert second["answer"] == "1 month"
    assert second.get("ask_user") is not True
    # And it survives via the profile row (progressive profiling).
    prof = profiles.get_profile(uow, uid)
    assert "Notice period" in (prof.get("form_answers") or "")
