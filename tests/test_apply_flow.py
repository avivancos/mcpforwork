"""Application state machine + start_application preflight (S4.1).

THE consent invariant: no submit-class step is ever emitted by the step
builder or preflight — only request_submit (S4.3) can route submission.
"""

import json

import pytest

from mcpforwork.adapters.db.backend import SqlUnitOfWork
from mcpforwork.domain.apply_flow import (
    ALLOWED_TRANSITIONS,
    STEP_KINDS,
    build_steps,
    can_transition,
)
from mcpforwork.services import apply as apply_service
from mcpforwork.services import dedup, hunt, profiles, review

_FINDING = {
    "url": "https://x.com/jobs/1",
    "title": "Data Engineer",
    "company_name": "Acme",
    "description": "Python pipelines.",
}


def _seed(
    uow: SqlUnitOfWork, approve: bool = True, email: str = "u@example.com"
) -> tuple[int, int]:
    uid = uow.insert("INSERT INTO users (email) VALUES (?)", (email,))
    profiles.create_profile(
        uow,
        uid,
        {"full_name": "Ada", "contact_email": "ada@x.com", "target_titles": ["Data Engineer"]},
    )
    hunt.submit_findings(uow, uid, "weworkremotely", [_FINDING])
    fid = hunt.list_matches(uow, uid, min_score=0)[0]["id"]
    if approve:
        review.approve_match(uow, uid, fid)
    uow.commit()
    return uid, fid


# ---------------------------------------------------------------- domain --- #
def test_submit_is_not_a_constructible_step_kind() -> None:
    assert "submit" not in STEP_KINDS  # structural: the builder cannot emit it


def test_build_steps_never_emits_a_submit_step() -> None:
    # Property over representative inputs: with/without assets and playbook.
    finding = {"url": "https://x.com/1", "title": "T", "source_slug": "reed"}
    profile = {"full_name": "Ada", "contact_email": "a@x.com"}
    for assets in ([], [{"asset_type": "cv", "version": 1}]):
        for playbook in ({}, {"ats_hint": "greenhouse", "quirks": "two pages"}):
            steps = build_steps(finding, profile, assets, playbook)
            assert steps, "steps must not be empty"
            assert all(s["kind"] in STEP_KINDS for s in steps)
            assert all(s["kind"] != "submit" for s in steps)
            assert steps[-1]["kind"] == "review"  # ends at human review, not submit


def test_transitions_enforced() -> None:
    assert can_transition("draft", "filling")
    assert can_transition("filling", "awaiting_human")
    assert can_transition("awaiting_human", "submit_requested")  # via request_submit only
    assert can_transition("submit_requested", "submitted")
    assert can_transition("submitted", "verified")
    assert not can_transition("draft", "submitted")  # cannot skip the human
    assert not can_transition("awaiting_human", "submitted")  # confirm needs a request first
    assert not can_transition("submitted", "filling")
    assert not can_transition("submitted", "awaiting_human")  # no post-submit regression
    assert "submitted" not in ALLOWED_TRANSITIONS["draft"]


# -------------------------------------------------------------- preflight --- #
def test_start_application_returns_a_session_with_steps(uow: SqlUnitOfWork) -> None:
    uid, fid = _seed(uow)
    session = apply_service.start_application(uow, uid, fid)
    uow.commit()
    assert session["state"] == "filling"
    assert session["consent_level"] == 0
    assert session["steps"][0]["kind"] == "navigate"
    assert all(s["kind"] != "submit" for s in session["steps"])
    row = uow.fetchone(
        "SELECT state, steps FROM applications WHERE id = ?", (session["application_id"],)
    )
    assert row["state"] == "filling"
    assert json.loads(row["steps"])  # persisted


def test_preflight_blocks_an_unapproved_finding(uow: SqlUnitOfWork) -> None:
    uid, fid = _seed(uow, approve=False)
    assert "error" in apply_service.start_application(uow, uid, fid)


def test_preflight_blocks_an_already_applied_url(uow: SqlUnitOfWork) -> None:
    uid, fid = _seed(uow)
    dedup.record_application(uow, uid, url=_FINDING["url"], channel="email")
    uow.commit()
    result = apply_service.start_application(uow, uid, fid)
    assert "error" in result and "applied" in result["error"]


def test_preflight_enforces_the_daily_cap(uow: SqlUnitOfWork) -> None:
    uid, fid = _seed(uow)
    # Fill today's quota with existing application rows.
    for i in range(apply_service.MAX_APPLICATIONS_PER_DAY):
        hunt.submit_findings(
            uow, uid, "weworkremotely", [{"url": f"https://cap.com/{i}", "title": "Data Engineer"}]
        )
        other = [m for m in hunt.list_matches(uow, uid, min_score=0) if f"cap.com/{i}" in m["url"]][
            0
        ]
        review.approve_match(uow, uid, other["id"])
        assert "error" not in apply_service.start_application(uow, uid, other["id"])
    uow.commit()
    result = apply_service.start_application(uow, uid, fid)
    assert "error" in result and "cap" in result["error"].lower()


def test_foreign_finding_rejected(uow: SqlUnitOfWork) -> None:
    uid, fid = _seed(uow)
    other = uow.insert("INSERT INTO users (email) VALUES (?)", ("b@example.com",))
    assert "error" in apply_service.start_application(uow, other, fid)


def test_double_start_for_the_same_finding_returns_the_open_application(
    uow: SqlUnitOfWork,
) -> None:
    uid, fid = _seed(uow)
    first = apply_service.start_application(uow, uid, fid)
    second = apply_service.start_application(uow, uid, fid)
    uow.commit()
    assert second["application_id"] == first["application_id"]  # idempotent re-open


@pytest.mark.parametrize("state", ["draft", "filling", "awaiting_human"])
def test_states_are_members_of_the_machine(state: str) -> None:
    assert state in ALLOWED_TRANSITIONS
