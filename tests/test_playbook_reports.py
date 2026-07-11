"""report_playbook_result capture + obstacle pause/resume round-trip (S4.4)."""

from mcpforwork.adapters.db.backend import SqlUnitOfWork
from mcpforwork.services import apply as apply_service
from mcpforwork.services import hunt, playbooks, profiles, review


def _user(uow: SqlUnitOfWork) -> int:
    return uow.insert("INSERT INTO users (email) VALUES (?)", ("u@example.com",))


def test_report_persists_and_validates(uow: SqlUnitOfWork) -> None:
    uid = _user(uow)
    result = playbooks.report_playbook_result(
        uow, uid, "reed", "drift", {"moved": "the apply button is now in a modal"}
    )
    uow.commit()
    assert result["ok"] is True
    row = uow.fetchone(
        "SELECT source_slug, kind, diff FROM playbook_reports WHERE user_id = ?", (uid,)
    )
    assert row["source_slug"] == "reed"
    assert "modal" in row["diff"]


def test_unknown_source_or_kind_rejected(uow: SqlUnitOfWork) -> None:
    uid = _user(uow)
    assert "error" in playbooks.report_playbook_result(uow, uid, "nope", "drift", {})
    assert "error" in playbooks.report_playbook_result(uow, uid, "reed", "meh", {})


def test_obstacle_pause_then_resume_completes_the_step(uow: SqlUnitOfWork) -> None:
    uid = _user(uow)
    profiles.create_profile(uow, uid, {"full_name": "Ada", "target_titles": ["DE"]})
    hunt.submit_findings(uow, uid, "weworkremotely", [{"url": "https://x.com/1", "title": "DE"}])
    fid = hunt.list_matches(uow, uid, min_score=0)[0]["id"]
    review.approve_match(uow, uid, fid)
    session = apply_service.start_application(uow, uid, fid)
    app_id, first = session["application_id"], session["steps"][0]
    uow.commit()

    paused = apply_service.report_apply_progress(
        uow, uid, app_id, first["step_id"], "blocked", obstacle="captcha"
    )
    assert paused["pause"] is True
    # Human solved it in their browser; the client resumes with ok.
    resumed = apply_service.report_apply_progress(uow, uid, app_id, first["step_id"], "ok")
    uow.commit()
    assert resumed["next_step"]["step_id"] == first["step_id"] + 1
