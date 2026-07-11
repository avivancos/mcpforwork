"""profile_gaps: progressive Tier 2 prompting data (S5.2)."""

import json

from mcpforwork.adapters.db.backend import SqlUnitOfWork
from mcpforwork.entrypoints.mcp import server
from mcpforwork.services import profiles


def test_empty_profile_lists_required_gaps_first(uow: SqlUnitOfWork) -> None:
    uid = uow.insert("INSERT INTO users (email) VALUES (?)", ("u@example.com",))
    profiles.create_profile(uow, uid, {})
    uow.commit()
    gaps = profiles.profile_gaps(uow, uid)
    assert gaps[0]["tier"] == 1  # required gaps first
    fields = [g["field"] for g in gaps]
    assert "target_titles" in fields
    assert "achievements" in fields  # tier 2
    assert fields.index("target_titles") < fields.index("achievements")
    assert all(g["why"] for g in gaps)


def test_rich_profile_has_few_or_no_gaps(uow: SqlUnitOfWork) -> None:
    uid = uow.insert("INSERT INTO users (email) VALUES (?)", ("u@example.com",))
    pid = profiles.create_profile(
        uow,
        uid,
        {
            "full_name": "Ada",
            "contact_email": "a@x.com",
            "country": "GB",
            "work_auth_countries": ["GB"],
            "target_titles": ["DE"],
            "sectors": ["tech"],
            "seniority": "senior",
            "employment_types": ["full_time"],
            "work_modes": ["remote"],
            "languages": [{"lang": "en"}],
            "cv_text": "cv",
            "links": {"github": "https://g"},
            "deal_breakers": ["on-call"],
            "availability_date": "2026-08-01",
        },
    )
    profiles.add_achievements(uow, uid, pid, [{"metric": "x"}])
    profiles.set_style_profile(uow, uid, pid, "sample")
    uow.commit()
    assert profiles.profile_gaps(uow, uid) == []


def test_no_profile_returns_setup_gap(uow: SqlUnitOfWork) -> None:
    uid = uow.insert("INSERT INTO users (email) VALUES (?)", ("u@example.com",))
    gaps = profiles.profile_gaps(uow, uid)
    assert gaps[0]["field"] == "profile"


def test_profile_gaps_tool(mcp_env) -> None:
    server.update_profile({"target_titles": ["DE"]})
    result = json.loads(server.profile_gaps())
    assert result["count"] >= 1
    assert all("why" in g for g in result["gaps"])
