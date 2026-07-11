"""ats_coverage_check: covered / missing-but-have / genuine-gap (S3.3)."""

from mcpforwork.adapters.db.backend import SqlUnitOfWork
from mcpforwork.domain.coverage import coverage_check
from mcpforwork.services import assets, coverage, hunt, profiles


def test_three_way_classification() -> None:
    keywords = ["python", "airflow", "kubernetes"]
    asset = "I build pipelines in Python."
    facts = "Python, Airflow DAGs at Acme."  # has airflow, not kubernetes
    result = coverage_check(keywords, asset, facts)
    assert result["covered"] == ["python"]
    assert result["missing_but_have"] == ["airflow"]  # truthfully addable
    assert result["genuine_gaps"] == ["kubernetes"]  # must be acknowledged
    assert result["coverage_pct"] == 33


def test_plural_and_case_variants_match() -> None:
    result = coverage_check(["pipelines", "KUBERNETES"], "Pipeline work on kubernetes.", "")
    assert set(result["covered"]) == {"pipelines", "kubernetes"}
    assert result["genuine_gaps"] == []


def test_empty_keywords_yield_full_coverage_shape() -> None:
    result = coverage_check([], "anything", "facts")
    assert result == {
        "covered": [],
        "missing_but_have": [],
        "genuine_gaps": [],
        "coverage_pct": 100,
    }


def test_schema_column_names_are_not_claimable_facts(uow: SqlUnitOfWork) -> None:
    # Gate P1 regression: a posting keyword equal to a profile COLUMN NAME
    # (e.g. "relocation") must NOT classify as missing_but_have when the user
    # never entered such a fact — schema keys are not the user's words.
    uid = uow.insert("INSERT INTO users (email) VALUES (?)", ("k@example.com",))
    profiles.create_profile(uow, uid, {"target_titles": ["Clerk"]})  # no relocation set
    hunt.submit_findings(
        uow,
        uid,
        "weworkremotely",
        [{"url": "https://x.com/k", "title": "Clerk", "description": "Relocation required."}],
    )
    uow.commit()
    fid = hunt.list_matches(uow, uid, min_score=0)[0]["id"]
    aid = assets.submit_asset(uow, uid, fid, "cv", "I file documents.")["asset_id"]
    uow.commit()
    result = coverage.ats_coverage_check(uow, uid, fid, aid)
    assert "relocation" in result["genuine_gaps"]
    assert "relocation" not in result["missing_but_have"]


def test_deterministic_same_inputs_same_output() -> None:
    args = (["a1", "b2"], "a1 text", "b2 facts")
    assert coverage_check(*args) == coverage_check(*args)


def _seed(uow: SqlUnitOfWork) -> tuple[int, int, int]:
    uid = uow.insert("INSERT INTO users (email) VALUES (?)", ("u@example.com",))
    profiles.create_profile(
        uow,
        uid,
        {"target_titles": ["Data Engineer"], "cv_text": "Python and Airflow pipelines at Acme."},
    )
    hunt.submit_findings(
        uow,
        uid,
        "weworkremotely",
        [
            {
                "url": "https://x.com/1",
                "title": "Data Engineer",
                "description": (
                    "Python, Airflow and Kubernetes. Kubernetes required. Airflow daily."
                ),
            }
        ],
    )
    uow.commit()
    fid = hunt.list_matches(uow, uid, min_score=0)[0]["id"]
    submitted = assets.submit_asset(uow, uid, fid, "cover_letter", "I write Python every day.")
    uow.commit()
    return uid, fid, submitted["asset_id"]


def test_service_flags_a_genuine_gap_without_stuffing(uow: SqlUnitOfWork) -> None:
    # Demo-gate criterion: the posting requires kubernetes; the profile lacks it;
    # the draft omits it -> genuine_gap (acknowledge, never stuff). Airflow is in
    # the profile but not the draft -> missing_but_have.
    uid, fid, aid = _seed(uow)
    result = coverage.ats_coverage_check(uow, uid, fid, aid)
    assert "kubernetes" in result["genuine_gaps"]
    assert "airflow" in result["missing_but_have"]
    assert "python" in result["covered"]


def test_service_rejects_foreign_or_unknown_ids(uow: SqlUnitOfWork) -> None:
    uid, fid, aid = _seed(uow)
    other = uow.insert("INSERT INTO users (email) VALUES (?)", ("b@example.com",))
    assert "error" in coverage.ats_coverage_check(uow, other, fid, aid)
    assert "error" in coverage.ats_coverage_check(uow, uid, fid, 9999)
