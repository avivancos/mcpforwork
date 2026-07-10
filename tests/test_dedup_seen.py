"""check_seen / record_application / recompute_hashes on SQLite."""

from mcpforwork.adapters.db.backend import SqlUnitOfWork
from mcpforwork.domain.dedup import dedup_hash
from mcpforwork.services import dedup


def _make_user(uow: SqlUnitOfWork, email: str) -> int:
    return uow.insert("INSERT INTO users (email) VALUES (?)", (email,))


def test_unseen_url_is_recommended_new(uow: SqlUnitOfWork) -> None:
    user_id = _make_user(uow, "u@example.com")
    result = dedup.check_seen(uow, user_id, ["https://example.com/jobs/77"])
    assert result["new_count"] == 1
    assert result["seen_count"] == 0
    assert result["items"][0]["recommendation"] == "new"
    assert result["items"][0]["seen"] is False


def test_check_seen_ignores_blank_and_whitespace_urls_in_a_batch(uow: SqlUnitOfWork) -> None:
    user_id = _make_user(uow, "u@example.com")
    result = dedup.check_seen(
        uow, user_id, ["https://example.com/jobs/77", "", "   ", "https://example.com/jobs/88"]
    )
    # Only the two non-blank URLs are accounted for.
    assert result["checked"] == 2
    assert result["new_count"] == 2
    assert [i["url"] for i in result["items"]] == [
        "https://example.com/jobs/77",
        "https://example.com/jobs/88",
    ]


def test_check_seen_reports_each_occurrence_of_a_duplicated_url(uow: SqlUnitOfWork) -> None:
    user_id = _make_user(uow, "u@example.com")
    result = dedup.check_seen(
        uow, user_id, ["https://example.com/jobs/77", "https://example.com/jobs/77"]
    )
    # Same URL twice in one batch yields two stable items, both "new".
    assert result["checked"] == 2
    assert [i["recommendation"] for i in result["items"]] == ["new", "new"]


def test_recorded_application_is_then_seen_and_skipped(uow: SqlUnitOfWork) -> None:
    user_id = _make_user(uow, "u@example.com")
    dedup.record_application(uow, user_id, url="https://example.com/jobs/77", channel="email")
    uow.commit()

    result = dedup.check_seen(uow, user_id, ["https://example.com/jobs/77"])
    item = result["items"][0]
    assert item["seen"] is True
    assert item["applied"] is True
    assert item["recommendation"] == "skip"
    assert item["source"] == "external_application"


def test_check_seen_matches_across_tracking_param_variants(uow: SqlUnitOfWork) -> None:
    # A URL applied via one dirty variant is seen when checked via another.
    user_id = _make_user(uow, "u@example.com")
    dedup.record_application(
        uow, user_id, url="https://www.linkedin.com/jobs/view/123/?eBP=x&refId=y"
    )
    uow.commit()

    result = dedup.check_seen(uow, user_id, ["http://linkedin.com/jobs/view/123?utm_source=z"])
    assert result["items"][0]["recommendation"] == "skip"


def test_record_application_is_idempotent_by_dedup_hash(uow: SqlUnitOfWork) -> None:
    user_id = _make_user(uow, "u@example.com")
    first = dedup.record_application(uow, user_id, url="https://example.com/jobs/77")
    second = dedup.record_application(
        uow, user_id, url="https://example.com/jobs/77/?utm_source=x", notes="second"
    )
    uow.commit()

    assert first["deduped"] is False
    assert second["deduped"] is True
    assert first["external_application_id"] == second["external_application_id"]
    count = uow.fetchone(
        "SELECT COUNT(*) AS n FROM external_applications WHERE user_id = ?", (user_id,)
    )
    assert count["n"] == 1


def test_record_application_requires_a_url(uow: SqlUnitOfWork) -> None:
    user_id = _make_user(uow, "u@example.com")
    result = dedup.record_application(uow, user_id, url="   ")
    assert "error" in result


def test_record_application_writes_an_audit_row(uow: SqlUnitOfWork) -> None:
    user_id = _make_user(uow, "u@example.com")
    dedup.record_application(uow, user_id, url="https://example.com/jobs/77", channel="web")
    uow.commit()
    audit = uow.fetchone(
        "SELECT action, detail FROM audit_log WHERE user_id = ? AND action = 'record_application'",
        (user_id,),
    )
    assert audit is not None
    assert '"channel": "web"' in audit["detail"]


def test_a_user_cannot_see_another_users_applications(uow: SqlUnitOfWork) -> None:
    alice = _make_user(uow, "alice@example.com")
    bob = _make_user(uow, "bob@example.com")
    dedup.record_application(uow, alice, url="https://example.com/jobs/77")
    uow.commit()
    # Bob checking the same URL sees it as new (app-level isolation by user_id).
    assert (
        dedup.check_seen(uow, bob, ["https://example.com/jobs/77"])["items"][0]["recommendation"]
        == "new"
    )


def test_recompute_merges_stale_tracking_param_duplicates(uow: SqlUnitOfWork) -> None:
    # Simulate two rows stored (via direct SQL, pre-canonicalisation) with
    # different stale hashes for URLs that canonicalise to the same posting.
    user_id = _make_user(uow, "u@example.com")
    clean = "https://example.com/jobs/77"
    dirty = "https://example.com/jobs/77/?utm_source=x"
    older = uow.insert(
        "INSERT INTO external_applications (user_id, url, channel, dedup_hash)"
        " VALUES (?, ?, 'email', ?)",
        (user_id, clean, "stale-hash-A"),
    )
    uow.insert(
        "INSERT INTO external_applications (user_id, url, channel, dedup_hash)"
        " VALUES (?, ?, 'web', ?)",
        (user_id, dirty, "stale-hash-B"),
    )
    uow.commit()

    report = dedup.recompute_hashes(uow, user_id)
    uow.commit()

    assert report["merged"] == 1
    rows = uow.fetchall(
        "SELECT id, dedup_hash FROM external_applications WHERE user_id = ?", (user_id,)
    )
    assert len(rows) == 1  # duplicates merged
    assert rows[0]["id"] == older  # lower id survives
    assert rows[0]["dedup_hash"] == dedup_hash(clean)


def test_recompute_is_idempotent_second_run_only_skips(uow: SqlUnitOfWork) -> None:
    user_id = _make_user(uow, "u@example.com")
    dedup.record_application(uow, user_id, url="https://example.com/jobs/77")
    uow.commit()

    first = dedup.recompute_hashes(uow, user_id)
    uow.commit()
    second = dedup.recompute_hashes(uow, user_id)
    uow.commit()
    # Freshly recorded rows already carry the canonical hash, so nothing changes.
    assert first == {"updated": 0, "merged": 0, "skipped": 1}
    assert second == {"updated": 0, "merged": 0, "skipped": 1}
