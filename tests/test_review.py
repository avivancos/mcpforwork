"""approve_match / discard_match + the four prompts (S3.4)."""

import asyncio

from mcpforwork.adapters.db.backend import SqlUnitOfWork
from mcpforwork.entrypoints.mcp import server
from mcpforwork.services import dedup, hunt, profiles, review


def _seed(uow: SqlUnitOfWork, email: str = "u@example.com") -> tuple[int, int]:
    uid = uow.insert("INSERT INTO users (email) VALUES (?)", (email,))
    profiles.create_profile(uow, uid, {"target_titles": ["Data Engineer"]})
    hunt.submit_findings(
        uow, uid, "weworkremotely", [{"url": "https://x.com/1", "title": "Data Engineer"}]
    )
    uow.commit()
    return uid, hunt.list_matches(uow, uid, min_score=0)[0]["id"]


def test_approve_flips_status_and_audits(uow: SqlUnitOfWork) -> None:
    uid, fid = _seed(uow)
    result = review.approve_match(uow, uid, fid)
    uow.commit()
    assert result["ok"] is True
    assert hunt.get_match(uow, uid, fid)["status"] == "approved"
    audit = uow.fetchone(
        "SELECT detail FROM audit_log WHERE user_id = ? AND action = 'approve_match'", (uid,)
    )
    assert audit is not None


def test_discard_flips_status_and_check_seen_reports_it(uow: SqlUnitOfWork) -> None:
    uid, fid = _seed(uow)
    review.discard_match(uow, uid, fid, reason="not remote")
    uow.commit()
    match = hunt.get_match(uow, uid, fid)
    assert match["status"] == "discarded"
    item = dedup.check_seen(uow, uid, ["https://x.com/1"])["items"][0]
    assert item["discarded"] is True
    assert item["recommendation"] == "skip"


def test_approve_a_discarded_match_errors(uow: SqlUnitOfWork) -> None:
    uid, fid = _seed(uow)
    review.discard_match(uow, uid, fid)
    uow.commit()
    assert "error" in review.approve_match(uow, uid, fid)


def test_foreign_or_unknown_finding_rejected(uow: SqlUnitOfWork) -> None:
    uid, fid = _seed(uow)
    other = uow.insert("INSERT INTO users (email) VALUES (?)", ("b@example.com",))
    assert "error" in review.approve_match(uow, other, fid)
    assert "error" in review.discard_match(uow, uid, 9999)


def test_all_four_prompts_are_registered_and_state_invariants() -> None:
    prompts = {p.name for p in asyncio.run(server.mcp.list_prompts())}
    assert {"setup", "hunt", "review", "apply"} <= prompts
    apply_text = server.apply_session()
    assert "facts_inventory" in apply_text
    assert "never" in apply_text.lower()  # never fabricate / never auto-submit
    setup_text = server.setup_session()
    assert "update_profile" in setup_text
