"""UK + Spain geo packs load, validate, and select correctly (S2.5).

The exact search URLs are browser-verified; these tests pin the structural
contract (country selection, http(s) {query} templates, no duplicate slugs).
"""

from mcpforwork.packs import registry

# Slugs whose search URLs were browser-verified to return real listings with the
# quote_plus (+-encoded) {query} the search_url() helper produces. Totaljobs /
# CV-Library were dropped — they are path-SEO portals that take the `+` literally.
_UK_SLUGS = {"indeed-uk", "reed", "adzuna-uk", "linkedin-uk"}
_ES_SLUGS = {"infojobs", "indeed-es", "linkedin-es", "tecnoempleo"}


def test_uk_pack_sources_are_selected_for_gb() -> None:
    gb = {s.slug for s in registry.sources_for(countries=["GB"])}
    assert gb >= _UK_SLUGS


def test_es_pack_sources_are_selected_for_es() -> None:
    es = {s.slug for s in registry.sources_for(countries=["ES"])}
    assert es >= _ES_SLUGS


def test_uk_boards_are_not_selected_for_a_spain_only_query() -> None:
    es = {s.slug for s in registry.sources_for(countries=["ES"])}
    assert not (_UK_SLUGS & es)  # GB-tagged boards excluded for an ES query


def test_every_geo_source_renders_an_http_search_url_with_the_query() -> None:
    sources = registry.load_sources()
    for slug in _UK_SLUGS | _ES_SLUGS:
        src = sources[slug]
        url = src.search_url("data engineer")
        assert url.startswith("https://")
        assert "{query}" not in url  # the placeholder was filled
        assert "data" in url.lower()  # the query made it into the URL


def test_global_remote_boards_still_match_gb_and_es() -> None:
    # "global" country tag matches any country, so remote boards appear too.
    gb = {s.slug for s in registry.sources_for(countries=["GB"])}
    es = {s.slug for s in registry.sources_for(countries=["ES"])}
    assert "remoteok" in gb
    assert "remoteok" in es


def test_all_shipped_packs_including_geo_load_without_duplicate_slugs() -> None:
    # load_sources() raises PackError on a duplicate slug across packs.
    sources = registry.load_sources()
    assert set(sources) >= _UK_SLUGS
    assert set(sources) >= _ES_SLUGS
