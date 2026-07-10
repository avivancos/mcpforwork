"""Profile services on SQLite: intake round-trip, validation, privacy, isolation."""

import pytest

from mcpforwork.adapters.db.backend import SqlUnitOfWork
from mcpforwork.domain.profile import ProfileValidationError
from mcpforwork.services import profiles


def _make_user(uow: SqlUnitOfWork, email: str) -> int:
    return uow.insert("INSERT INTO users (email) VALUES (?)", (email,))


TIER1 = {
    "full_name": "Ada Lovelace",
    "contact_email": "ada@example.com",
    "country": "GB",
    "city": "London",
    "work_auth_countries": ["GB", "EU"],
    "needs_sponsorship": 0,
    "target_titles": ["Backend Engineer", "Platform Engineer"],
    "sectors": ["fintech", "developer-tools"],
    "seniority": "senior",
    "employment_types": ["full_time", "contract"],
    "work_modes": ["remote", "hybrid"],
    "relocation": 1,
    "min_salary_amount": 90000,
    "min_salary_currency": "GBP",
    "min_salary_period": "year",
    "languages": [{"lang": "en", "level": "native"}],
    "cv_text": "Experienced backend engineer...",
}


def test_create_and_read_round_trips_tier1_fields(uow: SqlUnitOfWork) -> None:
    user_id = _make_user(uow, "ada@example.com")
    pid = profiles.create_profile(uow, user_id, TIER1)
    uow.commit()

    got = profiles.get_profile(uow, user_id)
    assert got["id"] == pid
    assert got["target_titles"] == ["Backend Engineer", "Platform Engineer"]
    assert got["languages"] == [{"lang": "en", "level": "native"}]
    assert got["seniority"] == "senior"
    assert got["is_active"] == 1


def test_update_applies_a_partial_patch(uow: SqlUnitOfWork) -> None:
    user_id = _make_user(uow, "ada@example.com")
    pid = profiles.create_profile(uow, user_id, TIER1)
    uow.commit()

    profiles.update_profile(uow, user_id, pid, {"city": "Manchester", "work_modes": ["remote"]})
    uow.commit()

    got = profiles.get_profile(uow, user_id, pid)
    assert got["city"] == "Manchester"
    assert got["work_modes"] == ["remote"]
    assert got["country"] == "GB"  # untouched


def test_invalid_seniority_is_rejected(uow: SqlUnitOfWork) -> None:
    user_id = _make_user(uow, "x@example.com")
    with pytest.raises(ProfileValidationError):
        profiles.create_profile(uow, user_id, {"seniority": "wizard"})


def test_more_than_five_target_titles_is_rejected(uow: SqlUnitOfWork) -> None:
    user_id = _make_user(uow, "x@example.com")
    with pytest.raises(ProfileValidationError):
        profiles.create_profile(uow, user_id, {"target_titles": ["a", "b", "c", "d", "e", "f"]})


def test_unknown_field_is_rejected(uow: SqlUnitOfWork) -> None:
    user_id = _make_user(uow, "x@example.com")
    with pytest.raises(ProfileValidationError):
        profiles.create_profile(uow, user_id, {"favourite_colour": "blue"})


def test_creating_a_second_active_profile_deactivates_the_first(uow: SqlUnitOfWork) -> None:
    user_id = _make_user(uow, "ada@example.com")
    first = profiles.create_profile(uow, user_id, {"label": "backend"}, label="backend")
    second = profiles.create_profile(uow, user_id, {"label": "data"}, label="data")
    uow.commit()

    active = profiles.get_profile(uow, user_id)
    assert active["id"] == second
    assert {p["id"]: p["is_active"] for p in profiles.list_profiles(uow, user_id)} == {
        first: 0,
        second: 1,
    }


def test_set_active_profile_switches_the_active_one(uow: SqlUnitOfWork) -> None:
    user_id = _make_user(uow, "ada@example.com")
    first = profiles.create_profile(uow, user_id, {}, label="backend")
    profiles.create_profile(uow, user_id, {}, label="data")
    uow.commit()

    profiles.set_active_profile(uow, user_id, first)
    uow.commit()
    assert profiles.get_profile(uow, user_id)["id"] == first


def test_achievements_bank_appends_and_lists(uow: SqlUnitOfWork) -> None:
    user_id = _make_user(uow, "ada@example.com")
    pid = profiles.create_profile(uow, user_id, {})
    uow.commit()

    profiles.add_achievements(
        uow,
        user_id,
        pid,
        [
            {"metric": "Cut p99 latency 40%", "context": "checkout API", "role": "Lead"},
            {"metric": "Scaled to 2M users"},
        ],
    )
    uow.commit()

    bank = profiles.list_achievements(uow, user_id, pid)
    assert [a["metric"] for a in bank] == ["Cut p99 latency 40%", "Scaled to 2M users"]
    assert bank[0]["context"] == "checkout API"


def test_achievement_without_a_metric_is_rejected(uow: SqlUnitOfWork) -> None:
    user_id = _make_user(uow, "ada@example.com")
    pid = profiles.create_profile(uow, user_id, {})
    uow.commit()
    with pytest.raises(ProfileValidationError):
        profiles.add_achievements(uow, user_id, pid, [{"context": "no metric here"}])


def test_style_profile_upserts(uow: SqlUnitOfWork) -> None:
    user_id = _make_user(uow, "ada@example.com")
    pid = profiles.create_profile(uow, user_id, {})
    uow.commit()

    profiles.set_style_profile(uow, user_id, pid, "Dear team, ...", {"tone": "warm"})
    profiles.set_style_profile(uow, user_id, pid, "Hi all, ...", {"tone": "direct"})
    uow.commit()

    style = profiles.get_style_profile(uow, user_id, pid)
    assert style["writing_sample"] == "Hi all, ..."
    assert style["directives"] == {"tone": "direct"}


def test_export_for_brief_redacts_minimum_salary_by_default(uow: SqlUnitOfWork) -> None:
    user_id = _make_user(uow, "ada@example.com")
    profiles.create_profile(uow, user_id, TIER1)
    uow.commit()

    redacted = profiles.export_for_brief(uow, user_id)
    assert "min_salary_amount" not in redacted
    assert "min_salary_currency" not in redacted
    assert "min_salary_period" not in redacted
    # non-private facts still present
    assert redacted["target_titles"] == ["Backend Engineer", "Platform Engineer"]


def test_export_for_brief_includes_salary_only_with_consent(uow: SqlUnitOfWork) -> None:
    user_id = _make_user(uow, "ada@example.com")
    profiles.create_profile(uow, user_id, TIER1)
    uow.commit()

    disclosed = profiles.export_for_brief(uow, user_id, disclose_salary=True)
    assert disclosed["min_salary_amount"] == 90000
    assert disclosed["min_salary_currency"] == "GBP"


def test_a_user_cannot_read_another_users_profile(uow: SqlUnitOfWork) -> None:
    alice = _make_user(uow, "alice@example.com")
    bob = _make_user(uow, "bob@example.com")
    alice_pid = profiles.create_profile(uow, alice, {"full_name": "Alice"})
    uow.commit()

    # app-level isolation: Bob asking for Alice's profile id gets nothing.
    assert profiles.get_profile(uow, bob, alice_pid) is None
    assert profiles.list_profiles(uow, bob) == []
    assert profiles.get_profile(uow, alice, alice_pid)["full_name"] == "Alice"
