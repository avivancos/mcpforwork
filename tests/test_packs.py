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
    # search_box sources are exempt: they carry no {query} in a navigable URL —
    # the client types the query into the board's on-page search box (S2.6).
    for slug, src in registry.load_sources().items():
        if src.mode != "url_template":
            continue
        before_query = src.url_template.split("?", 1)[0]
        assert "{query}" not in before_query, (
            f"{slug}: {{query}} must be in the query string, not the path"
        )


# --- S2.6: search_box playbook mode (SPA / Cloudflare boards) ---------------


def test_search_box_mode_does_not_require_query_in_the_url_template() -> None:
    # In search_box mode the template is a plain, navigable search PAGE — no
    # {query} to interpolate, because the client types the query on the page.
    pack = copy.deepcopy(_VALID)
    pack["sources"][0]["search_playbook"] = {
        "mode": "search_box",
        "url_template": "https://a.example.com/jobs",
        "result_hint": "Type '{query}' into the on-page search box, then read the cards.",
    }
    assert validate_pack(pack) == []


def test_url_template_mode_still_requires_the_query_placeholder() -> None:
    pack = copy.deepcopy(_VALID)
    pack["sources"][0]["search_playbook"] = {
        "mode": "url_template",
        "url_template": "https://a.example.com/jobs",  # no {query}
    }
    assert any("{query}" in e for e in validate_pack(pack))


def test_search_box_mode_requires_a_result_hint_that_names_the_query() -> None:
    # The hint IS the instruction ("type {query} here"); without it the client
    # would not know what to type or where.
    pack = copy.deepcopy(_VALID)
    pack["sources"][0]["search_playbook"] = {
        "mode": "search_box",
        "url_template": "https://a.example.com/jobs",
    }
    assert any("result_hint" in e for e in validate_pack(pack))
    pack["sources"][0]["search_playbook"]["result_hint"] = "just browse around"  # no {query}
    assert any("{query}" in e for e in validate_pack(pack))


def test_an_unknown_search_mode_is_rejected() -> None:
    pack = copy.deepcopy(_VALID)
    pack["sources"][0]["search_playbook"]["mode"] = "telepathy"
    assert any("mode" in e for e in validate_pack(pack))


def test_search_box_url_template_is_still_scheme_checked() -> None:
    # The template is handed to the user's browser to OPEN even in search_box
    # mode, so the http(s) guard must not be skipped (no javascript:/data:).
    pack = copy.deepcopy(_VALID)
    pack["sources"][0]["search_playbook"] = {
        "mode": "search_box",
        "url_template": "javascript:alert(1)",
        "result_hint": "type {query} into the box",
    }
    assert any("http(s)" in e for e in validate_pack(pack))


def test_a_search_box_source_that_forgets_mode_fails_loudly() -> None:
    # Realistic authoring mistake: a search-PAGE url_template (no {query}) written
    # WITHOUT `mode: search_box` defaults to url_template and must be rejected,
    # not silently shipped as a broken query-param source.
    pack = copy.deepcopy(_VALID)
    pack["sources"][0]["search_playbook"] = {
        "url_template": "https://a.example.com/jobs",  # no mode, no {query}
        "result_hint": "type {query} here",
    }
    assert any("{query}" in e for e in validate_pack(pack))


def test_absent_mode_defaults_to_url_template() -> None:
    # Back-compat: the country packs omit `mode` and must keep validating.
    pack = copy.deepcopy(_VALID)  # its search_playbook has no `mode`
    assert validate_pack(pack) == []
    assert registry._to_source(pack["sources"][0]).mode == "url_template"


def test_search_box_source_search_url_returns_the_navigable_page_unchanged() -> None:
    src = registry.load_sources()["remotive"]
    assert src.mode == "search_box"
    # No encoding, no {query} — it is the page the client opens before typing.
    assert src.search_url("data engineer") == src.url_template
    assert "{query}" not in src.search_url("data engineer")


def test_source_playbook_surfaces_the_search_mode() -> None:
    from mcpforwork.services import hunt

    pb = hunt.source_playbook("remotive", "data engineer")
    assert pb["mode"] == "search_box"
    assert pb["search_url"] == "https://remotive.com/remote-jobs"  # the page, not a filled template


def test_hunt_plan_surfaces_the_mode_per_source(uow) -> None:
    from mcpforwork.services import hunt, profiles

    uid = uow.insert("INSERT INTO users (email) VALUES (?)", ("u@example.com",))
    profiles.create_profile(
        uow, uid, {"target_titles": ["Data Engineer"], "work_modes": ["remote"]}
    )
    uow.commit()
    plan = hunt.hunt_plan(uow, uid)
    modes = {s["slug"]: s["mode"] for s in plan["sources"]}
    assert modes.get("remotive") == "search_box"  # a converted SPA board carries its mode


def test_global_remote_boards_are_verified_search_box_and_dead_boards_dropped() -> None:
    # S2.6 browser verification: none of the dedicated remote boards have a
    # working URL-param search, so every ENABLED one is search_box. hnhiring
    # (tag-index, no search box) and remoteok (paywalled search) are NOT shipped.
    sources = registry.load_sources()
    for slug in ("remotive", "weworkremotely", "himalayas", "jobicy", "workingnomads"):
        assert sources[slug].mode == "search_box", f"{slug} must be search_box"
        assert sources[slug].enabled
    assert "hnhiring" not in sources
    assert "remoteok" not in sources


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
