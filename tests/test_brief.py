"""Generation brief: deterministic extraction + the facts inventory (S3.1)."""

from mcpforwork.adapters.db.backend import SqlUnitOfWork
from mcpforwork.domain.brief import HONESTY_RULES, build_facts_inventory, extract_keywords
from mcpforwork.services import briefs, hunt, profiles

_DESCRIPTION = (
    "We need a Data Engineer to build data pipelines with Python and Airflow on AWS. "
    "You will own our Airflow DAGs and the data warehouse. Experience with dbt and "
    "Kubernetes is a plus. The role is remote within the UK."
)


def test_extract_keywords_is_deterministic_and_boosts_title_terms() -> None:
    first = extract_keywords("Senior Data Engineer", _DESCRIPTION)
    second = extract_keywords("Senior Data Engineer", _DESCRIPTION)
    assert first == second  # deterministic
    assert "data" in first and "engineer" in first  # title terms present
    assert "airflow" in first  # repeated body term extracted
    assert "the" not in first and "with" not in first  # stopwords out


def test_extract_keywords_empty_input_is_empty() -> None:
    assert extract_keywords("", "") == []


def test_facts_inventory_contains_only_profile_provable_claims() -> None:
    profile = {
        "full_name": "Ada",
        "target_titles": ["Data Engineer"],
        "sectors": ["fintech"],
        "seniority": "senior",
        "languages": [{"lang": "en", "level": "native"}],
        "links": {"github": "https://github.com/ada"},
        "cv_text": "Built pipelines at Acme.",
        "min_salary_amount": 90000,  # must NEVER surface
        "country": "GB",
    }
    achievements = [{"metric": "Cut costs 30%", "context": "ETL", "role": "Lead"}]
    inv = build_facts_inventory(profile, achievements)
    assert inv["identity"]["full_name"] == "Ada"
    assert inv["achievements"][0]["metric"] == "Cut costs 30%"
    assert "min_salary_amount" not in str(inv)  # salary KEY never in a brief
    assert "90000" not in str(inv)  # salary VALUE never in a brief either
    assert inv["gaps_policy"] == "acknowledge"


def test_title_terms_outrank_equal_frequency_body_terms() -> None:
    # "alpha" appears once in the title, "beta" once in the body: the title
    # boost must rank alpha first (golden ordering, kills a boost-removal mutant).
    ranked = extract_keywords("Alpha specialist", "beta tools daily. beta and gamma.")
    # alpha: title boost 3 > beta: frequency 2 > gamma: frequency 1
    assert ranked.index("alpha") < ranked.index("beta") < ranked.index("gamma")
    assert extract_keywords("Alpha specialist", "beta tools daily. beta and gamma.") == ranked


def test_facts_inventory_with_no_achievements_is_empty_not_invented() -> None:
    inv = build_facts_inventory({"full_name": "Ada"}, [])
    assert inv["achievements"] == []


def _seed_match(uow: SqlUnitOfWork) -> tuple[int, int]:
    uid = uow.insert("INSERT INTO users (email) VALUES (?)", ("u@example.com",))
    profiles.create_profile(
        uow, uid, {"full_name": "Ada", "target_titles": ["Data Engineer"], "cv_text": "Python."}
    )
    hunt.submit_findings(
        uow,
        uid,
        "weworkremotely",
        [{"url": "https://x.com/1", "title": "Data Engineer", "description": _DESCRIPTION}],
    )
    uow.commit()
    fid = hunt.list_matches(uow, uid, min_score=0)[0]["id"]
    return uid, fid


def test_get_generation_brief_assembles_job_facts_style_and_rules(uow: SqlUnitOfWork) -> None:
    uid, fid = _seed_match(uow)
    profiles.set_style_profile(uow, uid, profiles.get_profile(uow, uid)["id"], "Hi team,")
    uow.commit()

    brief = briefs.get_generation_brief(uow, uid, fid, "cover_letter")
    assert brief["job"]["title"] == "Data Engineer"
    assert "airflow" in brief["job"]["keywords"]
    assert brief["facts_inventory"]["identity"]["full_name"] == "Ada"
    assert brief["style"]["writing_sample"] == "Hi team,"
    assert brief["honesty_rules"] == list(HONESTY_RULES)
    assert brief["asset_type"] == "cover_letter"
    assert brief["format"]["medium"] == "markdown"


def test_brief_for_unknown_finding_or_missing_profile_errors(uow: SqlUnitOfWork) -> None:
    uid = uow.insert("INSERT INTO users (email) VALUES (?)", ("x@example.com",))
    assert "error" in briefs.get_generation_brief(uow, uid, 999, "cv")
    # finding exists but belongs to another user
    uid2, fid = _seed_match(uow)
    other = uow.insert("INSERT INTO users (email) VALUES (?)", ("y@example.com",))
    assert "error" in briefs.get_generation_brief(uow, other, fid, "cv")


def test_brief_rejects_unknown_asset_type(uow: SqlUnitOfWork) -> None:
    uid, fid = _seed_match(uow)
    assert "error" in briefs.get_generation_brief(uow, uid, fid, "poem")
