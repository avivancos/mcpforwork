"""Pack schema validation + the shipped seed packs load and select correctly."""

import copy

from mcpforwork.domain.packs import validate_pack
from mcpforwork.packs import registry

_VALID = {
    "pack": {"id": "demo", "version": 1, "kind": "global", "title": "Demo"},
    "sources": [
        {
            "slug": "board-a",
            "name": "Board A",
            "base_url": "https://a.example.com",
            "countries": ["global"],
            "sectors": ["any"],
            "remote": True,
            "tier": "free",
            "enabled": True,
            "search_playbook": {"url_template": "https://a.example.com/s?q={query}"},
        }
    ],
}


def test_a_well_formed_pack_has_no_errors() -> None:
    assert validate_pack(copy.deepcopy(_VALID)) == []


def test_missing_required_source_field_is_reported() -> None:
    bad = copy.deepcopy(_VALID)
    del bad["sources"][0]["name"]
    errors = validate_pack(bad)
    assert any("name" in e for e in errors)


def test_bad_country_code_is_rejected() -> None:
    bad = copy.deepcopy(_VALID)
    bad["sources"][0]["countries"] = ["usa"]  # not ISO alpha-2 nor "global"
    assert any("countries" in e for e in validate_pack(bad))


def test_url_template_without_query_placeholder_is_rejected() -> None:
    bad = copy.deepcopy(_VALID)
    bad["sources"][0]["search_playbook"]["url_template"] = "https://a.example.com/s"
    assert any("query" in e for e in validate_pack(bad))


def test_duplicate_slug_within_a_pack_is_rejected() -> None:
    bad = copy.deepcopy(_VALID)
    bad["sources"].append(copy.deepcopy(bad["sources"][0]))
    assert any("duplicate" in e.lower() for e in validate_pack(bad))


def test_unknown_tier_is_rejected() -> None:
    bad = copy.deepcopy(_VALID)
    bad["sources"][0]["tier"] = "enterprise"
    assert any("tier" in e for e in validate_pack(bad))


def test_bad_pack_kind_is_rejected() -> None:
    bad = copy.deepcopy(_VALID)
    bad["pack"]["kind"] = "sectorish"
    assert any("kind" in e for e in validate_pack(bad))


def test_all_shipped_packs_load_and_validate() -> None:
    sources = registry.load_sources()
    assert len(sources) >= 10  # a meaningful seed
    assert "remoteok" in sources
    # url_template renders with a query
    assert "{query}" not in sources["remoteok"].search_url("data engineer")


def test_sources_for_selects_by_country_and_remote() -> None:
    # A global-remote board is returned for any country when remote is wanted.
    remote_global = registry.sources_for(countries=["FR"], remote=True)
    assert any(s.slug == "remoteok" for s in remote_global)
    # A US-only board is not returned for a DE-only, onsite query.
    de_sources = registry.sources_for(countries=["DE"])
    assert all("US" not in s.countries for s in de_sources if "global" not in s.countries)


def test_sources_for_selects_by_sector() -> None:
    # Sector-tagged sources match a matching sector; "any" sources always match.
    tech = {s.slug for s in registry.sources_for(sectors=["tech"])}
    assert tech, "expected at least one source matching the tech sector"
