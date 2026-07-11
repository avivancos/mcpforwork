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


def test_non_http_url_template_is_rejected() -> None:
    # Packs are untrusted input; a javascript:/data: template must be rejected.
    bad = copy.deepcopy(_VALID)
    bad["sources"][0]["search_playbook"]["url_template"] = "javascript:alert(1)?q={query}"
    assert any("http" in e for e in validate_pack(bad))


def test_non_mapping_pack_is_rejected() -> None:
    assert validate_pack([1, 2, 3])


def test_missing_pack_block_is_rejected() -> None:
    assert any("pack" in e for e in validate_pack({"sources": _VALID["sources"]}))


def test_non_integer_version_is_rejected() -> None:
    bad = copy.deepcopy(_VALID)
    bad["pack"]["version"] = "one"
    assert any("version" in e for e in validate_pack(bad))


def test_empty_sources_is_rejected() -> None:
    assert any("sources" in e for e in validate_pack({"pack": _VALID["pack"], "sources": []}))


def test_non_http_base_url_is_rejected() -> None:
    bad = copy.deepcopy(_VALID)
    bad["sources"][0]["base_url"] = "ftp://x.example.com"
    assert any("base_url" in e for e in validate_pack(bad))


def test_non_bool_auto_apply_safe_is_rejected() -> None:
    bad = copy.deepcopy(_VALID)
    bad["sources"][0]["apply_playbook"] = {"auto_apply_safe": "yes"}
    assert any("auto_apply_safe" in e for e in validate_pack(bad))


def test_sources_for_excludes_a_non_matching_sector() -> None:
    # germantechjobs is tagged sectors:[tech]; a healthcare query must not select
    # it, but a tech query must.
    healthcare = {s.slug for s in registry.sources_for(sectors=["healthcare"])}
    assert "germantechjobs" not in healthcare
    tech = {s.slug for s in registry.sources_for(sectors=["tech"])}
    assert "germantechjobs" in tech


def test_no_shipped_template_puts_the_query_in_the_url_path() -> None:
    # search_url() quote_plus-encodes the query (space -> "+"), which only works
    # in the query string — a path segment takes the "+" literally. This guards
    # the bug class that got Totaljobs/CV-Library dropped and stepstone-de fixed:
    # every shipped url_template must be query-param style ({query} after "?").
    for slug, src in registry.load_sources().items():
        before_query = src.url_template.split("?", 1)[0]
        assert "{query}" not in before_query, (
            f"{slug}: {{query}} must be in the query string, not the path"
        )


def test_all_shipped_packs_load_and_validate() -> None:
    sources = registry.load_sources()
    assert len(sources) >= 10  # a meaningful seed
    assert "weworkremotely" in sources
    # url_template renders with a query
    assert "{query}" not in sources["weworkremotely"].search_url("data engineer")


def test_sources_for_selects_by_country_and_remote() -> None:
    # A global-remote board is returned for any country when remote is wanted.
    remote_global = registry.sources_for(countries=["FR"], remote=True)
    assert any(s.slug == "weworkremotely" for s in remote_global)
    # A US-only board is not returned for a DE-only, onsite query.
    de_sources = registry.sources_for(countries=["DE"])
    assert all("US" not in s.countries for s in de_sources if "global" not in s.countries)


def test_sources_for_selects_by_sector() -> None:
    # Sector-tagged sources match a matching sector; "any" sources always match.
    tech = {s.slug for s in registry.sources_for(sectors=["tech"])}
    assert tech, "expected at least one source matching the tech sector"
