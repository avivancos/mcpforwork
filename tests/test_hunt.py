"""Hunt service on SQLite: plan, ingest (dedup + score), list matches."""

from mcpforwork.adapters.db.backend import SqlUnitOfWork
from mcpforwork.services import dedup, hunt, profiles


def _user(uow: SqlUnitOfWork, email: str = "u@example.com") -> int:
    return uow.insert("INSERT INTO users (email) VALUES (?)", (email,))


def test_hunt_plan_returns_actionable_search_urls_for_the_active_profile(uow) -> None:
    uid = _user(uow)
    profiles.create_profile(
        uow,
        uid,
        {
            "target_titles": ["Data Engineer"],
            "work_auth_countries": ["US"],
            "work_modes": ["remote"],
        },
    )
    uow.commit()
    plan = hunt.hunt_plan(uow, uid)
    assert plan["count"] > 0
    assert all(s["search_url"].startswith("http") for s in plan["sources"])
    assert any("data" in s["search_url"].lower() for s in plan["sources"])


def test_hunt_plan_without_a_profile_returns_an_error(uow) -> None:
    uid = _user(uow)
    assert "error" in hunt.hunt_plan(uow, uid)


def test_submit_findings_dedups_scores_and_persists(uow) -> None:
    uid = _user(uow)
    profiles.create_profile(uow, uid, {"target_titles": ["Data Engineer"], "sectors": ["tech"]})
    uow.commit()

    first = hunt.submit_findings(
        uow,
        uid,
        "remoteok",
        [
            {
                "url": "https://remoteok.com/remote-jobs/123",
                "title": "Senior Data Engineer",
                "description": "Build data pipelines",
            },
            {"url": "", "title": "blank"},  # skipped (no url)
        ],
    )
    uow.commit()
    assert first["new"] == 1
    assert first["skipped"] == 1

    # The same posting via a dirty tracking-param variant is seen again, not new.
    second = hunt.submit_findings(
        uow,
        uid,
        "remoteok",
        [
            {
                "url": "https://remoteok.com/remote-jobs/123?utm_source=x",
                "title": "Senior Data Engineer",
            }
        ],
    )
    uow.commit()
    assert second["seen_again"] == 1

    matches = hunt.list_matches(uow, uid, min_score=1)
    assert len(matches) == 1
    assert matches[0]["title"] == "Senior Data Engineer"
    assert isinstance(matches[0]["score_breakdown"], dict)


def test_resighting_a_posting_with_less_data_does_not_downgrade_it(uow) -> None:
    # A rich first sighting then a sparse re-sight (just url+title): the stored
    # description/salary and the richer score must survive.
    uid = _user(uow)
    profiles.create_profile(
        uow, uid, {"target_titles": ["Registered Nurse"], "sectors": ["healthcare"]}
    )
    uow.commit()
    url = "https://x.com/1"
    hunt.submit_findings(
        uow,
        uid,
        "remoteok",
        [
            {
                "url": url,
                "title": "Registered Nurse",
                "description": "Critical care nursing in a healthcare unit",
                "salary_text": "$95k",
            }
        ],
    )
    uow.commit()
    rich_score = hunt.list_matches(uow, uid, min_score=0)[0]["score"]

    hunt.submit_findings(uow, uid, "remoteok", [{"url": url, "title": "Registered Nurse"}])
    uow.commit()
    match = hunt.list_matches(uow, uid, min_score=0)[0]
    assert match["score"] == rich_score  # not downgraded
    assert match["description"] == "Critical care nursing in a healthcare unit"  # not erased


def test_resighting_a_posting_with_more_data_enriches_it(uow) -> None:
    uid = _user(uow)
    profiles.create_profile(
        uow, uid, {"target_titles": ["Data Engineer"], "work_modes": ["remote"]}
    )
    uow.commit()
    url = "https://x.com/1"
    hunt.submit_findings(uow, uid, "remoteok", [{"url": url, "title": "Data Engineer"}])
    uow.commit()
    lean_score = hunt.list_matches(uow, uid, min_score=0)[0]["score"]

    hunt.submit_findings(
        uow,
        uid,
        "remoteok",
        [{"url": url, "title": "Data Engineer", "remote_scope": "remote", "salary_text": "$120k"}],
    )
    uow.commit()
    match = hunt.list_matches(uow, uid, min_score=0)[0]
    assert match["score"] > lean_score  # enriched by the remote + salary signals


def test_submit_findings_unknown_source_errors(uow) -> None:
    uid = _user(uow)
    assert "error" in hunt.submit_findings(uow, uid, "no-such-source", [])


def test_list_matches_orders_by_score_and_respects_min_score(uow) -> None:
    uid = _user(uow)
    profiles.create_profile(uow, uid, {"target_titles": ["Data Engineer"]})
    uow.commit()
    hunt.submit_findings(
        uow,
        uid,
        "remoteok",
        [
            {"url": "https://x.com/1", "title": "Data Engineer", "description": "data pipelines"},
            {"url": "https://x.com/2", "title": "Chef", "description": "cooking in a kitchen"},
        ],
    )
    uow.commit()
    high = hunt.list_matches(uow, uid, min_score=1)
    assert [m["title"] for m in high] == ["Data Engineer"]  # the chef scores 0
    everything = hunt.list_matches(uow, uid, min_score=0)
    assert len(everything) == 2
    assert everything[0]["score"] >= everything[1]["score"]  # best first


def test_a_scouted_finding_is_then_seen_by_check_seen(uow) -> None:
    uid = _user(uow)
    profiles.create_profile(uow, uid, {"target_titles": ["Data Engineer"]})
    uow.commit()
    hunt.submit_findings(
        uow, uid, "remoteok", [{"url": "https://x.com/1", "title": "Data Engineer"}]
    )
    uow.commit()
    seen = dedup.check_seen(uow, uid, ["https://x.com/1"])
    assert seen["items"][0]["recommendation"] == "skip"
    assert seen["items"][0]["source"] == "finding"


def test_a_finding_scouted_by_one_user_is_invisible_to_another(uow) -> None:
    alice = _user(uow, "alice@example.com")
    bob = _user(uow, "bob@example.com")
    profiles.create_profile(uow, alice, {"target_titles": ["Data Engineer"]})
    uow.commit()
    hunt.submit_findings(
        uow, alice, "remoteok", [{"url": "https://x.com/1", "title": "Data Engineer"}]
    )
    uow.commit()
    assert hunt.list_matches(uow, bob, min_score=0) == []
