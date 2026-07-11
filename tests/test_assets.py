"""submit_asset versioning + get_assets + ownership (S3.2)."""

from mcpforwork.adapters.db.backend import SqlUnitOfWork
from mcpforwork.services import assets, hunt, profiles


def _seed_match(uow: SqlUnitOfWork, email: str = "u@example.com") -> tuple[int, int]:
    uid = uow.insert("INSERT INTO users (email) VALUES (?)", (email,))
    profiles.create_profile(uow, uid, {"target_titles": ["Data Engineer"]})
    hunt.submit_findings(
        uow, uid, "weworkremotely", [{"url": f"https://x.com/{email}", "title": "Data Engineer"}]
    )
    uow.commit()
    return uid, hunt.list_matches(uow, uid, min_score=0)[0]["id"]


def test_versions_auto_increment_per_finding_and_type(uow: SqlUnitOfWork) -> None:
    uid, fid = _seed_match(uow)
    v1 = assets.submit_asset(uow, uid, fid, "cover_letter", "Dear team v1")
    v2 = assets.submit_asset(uow, uid, fid, "cover_letter", "Dear team v2")
    cv = assets.submit_asset(uow, uid, fid, "cv", "# CV")
    uow.commit()
    assert (v1["version"], v2["version"]) == (1, 2)
    assert cv["version"] == 1  # independent series per asset_type
    assert v2["asset_id"] != v1["asset_id"]


def test_get_assets_newest_first_and_filterable(uow: SqlUnitOfWork) -> None:
    uid, fid = _seed_match(uow)
    assets.submit_asset(uow, uid, fid, "cover_letter", "v1")
    assets.submit_asset(uow, uid, fid, "cover_letter", "v2")
    assets.submit_asset(uow, uid, fid, "cv", "cv1")
    uow.commit()
    all_rows = assets.get_assets(uow, uid, fid)
    assert [a["version"] for a in all_rows if a["asset_type"] == "cover_letter"] == [2, 1]
    only_cv = assets.get_assets(uow, uid, fid, asset_type="cv")
    assert len(only_cv) == 1 and only_cv[0]["content"] == "cv1"


def test_submit_against_a_foreign_finding_errors(uow: SqlUnitOfWork) -> None:
    _, fid = _seed_match(uow, "a@example.com")
    other = uow.insert("INSERT INTO users (email) VALUES (?)", ("b@example.com",))
    result = assets.submit_asset(uow, other, fid, "cv", "sneaky")
    assert "error" in result
    assert assets.get_assets(uow, other, fid) == []


def test_unknown_asset_type_errors(uow: SqlUnitOfWork) -> None:
    uid, fid = _seed_match(uow)
    assert "error" in assets.submit_asset(uow, uid, fid, "poem", "x")
