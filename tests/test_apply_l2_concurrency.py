"""L2 authorization under concurrency (S7.2d): the cap count and the consent
flip must be atomic ACROSS transactions, or N parallel `request_submit` calls
on distinct pre-staged applications each pass the cap check (TOCTOU). The fix
serializes count+flip per user (a no-op self-update on the users row takes the
write lock on both dialects); these tests run real threads against real SQLite
connections — zero mocks, time/sources injected.

Two distinct properties pinned:
- two-app, cap 1: without serialization BOTH would authorize (cap exceeded);
- same-app: the atomic consent_level guard writes exactly ONE authorization
  audit row even when two calls race the same application.
"""

import threading
from pathlib import Path

from mcpforwork.adapters.db import connect
from mcpforwork.services import apply as apply_service
from mcpforwork.services import autopilot, hunt, profiles, review

_SAFE = frozenset({"weworkremotely"})


def _stage(tmp_path: Path, n_apps: int, cap: int) -> tuple[str, int, list[int]]:
    """A user with `n_apps` filled applications at submit_requested and an
    active L2 policy with the given cap. Staging happens BEFORE the policy
    exists so the staging request_submit calls all land on await_human."""
    url = f"sqlite:///{tmp_path / 'l2concurrent.db'}"
    uow = connect(url)
    try:
        uid = uow.insert("INSERT INTO users (email) VALUES (?)", ("race@example.com",))
        profiles.create_profile(uow, uid, {"full_name": "Ada", "target_titles": ["Data Engineer"]})
        app_ids = []
        for i in range(n_apps):
            job_url = f"https://x.com/jobs/race-{i}"
            hunt.submit_findings(uow, uid, "weworkremotely", [{"url": job_url, "title": "DE"}])
            fid = uow.fetchone(
                "SELECT id FROM explore_findings WHERE url = ? AND user_id = ?", (job_url, uid)
            )["id"]
            uow.execute("UPDATE explore_findings SET score = 90 WHERE id = ?", (fid,))
            review.approve_match(uow, uid, fid)
            session = apply_service.start_application(uow, uid, fid)
            app_id = session["application_id"]
            for step in session["steps"]:
                apply_service.report_apply_progress(uow, uid, app_id, step["step_id"], "ok")
            decision = apply_service.request_submit(uow, uid, app_id, safe_sources=_SAFE)
            assert decision["decision"] == "await_human"  # no policy yet
            app_ids.append(app_id)
        autopilot.put_policy(uow, uid, min_score=0, max_per_day=cap)
        uow.commit()
        return url, uid, app_ids
    finally:
        uow.close()


def _race(url: str, uid: int, app_ids: list[int]) -> list[dict]:
    """One thread per application, all released on a barrier, each on its OWN
    connection (sqlite3 connections are single-thread). Connections are
    opened BEFORE the barrier: connect() runs migrations, whose final
    `PRAGMA user_version = N` is a database-header WRITE that would
    serialize the racers on the connection handshake instead of racing the
    authorization path."""
    barrier = threading.Barrier(len(app_ids))
    results: list[dict] = [{}] * len(app_ids)

    def call(idx: int, app_id: int) -> None:
        barrier.wait()
        # Migrations already ran in _stage: skipping them matters twice over —
        # the migration trailer's `PRAGMA user_version = N` is a header WRITE
        # that would serialize the racers at handshake time, and a connection
        # must be created in the thread that uses it (check_same_thread).
        uow = connect(url, run_migrations=False)
        try:
            results[idx] = apply_service.request_submit(uow, uid, app_id, safe_sources=_SAFE)
            uow.commit()
        finally:
            uow.close()

    threads = [threading.Thread(target=call, args=(i, a)) for i, a in enumerate(app_ids)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    return results


def _l2_audit_rows(url: str, uid: int) -> list[dict]:
    uow = connect(url)
    try:
        return uow.fetchall(
            "SELECT detail FROM audit_log WHERE user_id = ? AND action = 'submit_authorized'"
            " AND detail LIKE ?",
            (uid, '%"level": 2%'),
        )
    finally:
        uow.close()


def test_a_second_submit_counting_mid_first_transaction_is_refused_by_the_cap(
    tmp_path: Path,
) -> None:
    # The deterministic TOCTOU interleaving: T1 evaluates and flips app1 but
    # holds its transaction OPEN; T2 then runs the full request_submit path.
    # Serialized (the fix): T2 blocks on the per-user lock until T1 commits,
    # then counts 1 → cap refusal. Unserialized (the mutant): T2's count
    # reads 0 (SQLite SHARED reads coexist with T1's RESERVED write) and T2
    # authorizes too — cap 1 exceeded.
    url, uid, app_ids = _stage(tmp_path, n_apps=2, cap=1)
    entered = threading.Event()
    release = threading.Event()
    outcome: dict[str, dict] = {}

    def first() -> None:
        # run_migrations=False (already migrated in _stage): the migration
        # trailer's header write would otherwise serialize T2's handshake
        # behind T1's open transaction instead of racing the authz path.
        uow = connect(url, run_migrations=False)
        try:
            outcome["first"] = apply_service.request_submit(
                uow, uid, app_ids[0], safe_sources=_SAFE
            )
            entered.set()  # flip + audit written, transaction still open
            release.wait(timeout=5)  # hold the transaction open, then commit
            uow.commit()
        finally:
            uow.close()

    t = threading.Thread(target=first)
    t.start()
    assert entered.wait(timeout=10)
    second = connect(url, run_migrations=False)
    try:
        outcome["second"] = apply_service.request_submit(
            second, uid, app_ids[1], safe_sources=_SAFE
        )
        second.commit()
    finally:
        second.close()
    release.set()  # already committed via the 5s hold timeout if serialized
    t.join(timeout=15)

    assert outcome["first"]["decision"] == "submit_authorized"
    assert outcome["second"]["decision"] == "await_human", outcome
    assert "cap" in outcome["second"].get("reason", "")
    assert len(_l2_audit_rows(url, uid)) == 1


def test_parallel_submits_on_distinct_applications_never_exceed_the_cap(
    tmp_path: Path,
) -> None:
    # End-state invariant under real parallelism (4 racing applications, cap
    # 1): exactly one authorization, exactly one consent flip, three honest
    # cap refusals. The interleaved test above is the deterministic mutant
    # killer; this one pins the invariant under a barrier-synchronized race.
    url, uid, app_ids = _stage(tmp_path, n_apps=4, cap=1)
    results = _race(url, uid, app_ids)

    authorized = [r for r in results if r.get("decision") == "submit_authorized"]
    refused = [r for r in results if r.get("decision") == "await_human"]
    assert len(authorized) == 1, f"cap 1 but {len(authorized)} authorized: {results}"
    assert len(refused) == 3
    assert all("cap" in r.get("reason", "") for r in refused)
    assert len(_l2_audit_rows(url, uid)) == 1

    uow = connect(url)
    try:
        flipped = uow.fetchall(
            "SELECT id FROM applications WHERE user_id = ? AND consent_level = 2", (uid,)
        )
        assert len(flipped) == 1
    finally:
        uow.close()


def test_parallel_submits_on_the_same_application_write_exactly_one_authorization(
    tmp_path: Path,
) -> None:
    # The atomic consent_level 0→2 flip: two racing calls on the SAME
    # application both get the directive (a minted authorization is never
    # stranded), but exactly ONE authorization event exists — the loser's
    # conditional UPDATE matches 0 rows and must not write a second event.
    url, uid, app_ids = _stage(tmp_path, n_apps=1, cap=2)
    results = _race(url, uid, [app_ids[0], app_ids[0]])

    assert all(r.get("decision") == "submit_authorized" for r in results), results
    assert len(_l2_audit_rows(url, uid)) == 1
