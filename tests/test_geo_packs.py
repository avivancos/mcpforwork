"""UK + Spain geo packs load, validate, and select correctly (S2.5).

The exact search URLs are browser-verified; these tests pin the structural
contract (country selection, http(s) {query} templates, no duplicate slugs).
"""

from mcpforwork.packs import registry

# Slugs whose search URLs were browser-verified to return real listings with the
# quote_plus (+-encoded) {query} the search_url() helper produces. Totaljobs /
# CV-Library were dropped — they are path-SEO portals that take the `+` literally.
_UK_SLUGS = {"indeed-uk", "reed", "adzuna-uk", "linkedin-uk"}
_ES_SLUGS = {"infojobs", "indeed-es", "adzuna-es", "linkedin-es", "tecnoempleo"}


def test_uk_pack_sources_are_selected_for_gb() -> None:
    gb = {s.slug for s in registry.sources_for(countries=["GB"])}
    assert gb >= _UK_SLUGS


def test_es_pack_sources_are_selected_for_es() -> None:
    es = {s.slug for s in registry.sources_for(countries=["ES"])}
    assert es >= _ES_SLUGS


def test_uk_boards_are_not_selected_for_a_spain_only_query() -> None:
    es = {s.slug for s in registry.sources_for(countries=["ES"])}
    assert not (_UK_SLUGS & es)  # GB-tagged boards excluded for an ES query


def test_es_boards_are_not_selected_for_a_uk_only_query() -> None:
    gb = {s.slug for s in registry.sources_for(countries=["GB"])}
    assert not (_ES_SLUGS & gb)  # ES-tagged boards excluded for a GB query


def test_onsite_geo_boards_are_excluded_from_a_remote_only_query() -> None:
    remote_es = {s.slug for s in registry.sources_for(countries=["ES"], remote=True)}
    assert not (_ES_SLUGS & remote_es)  # onsite geo boards drop out when remote is wanted
    assert "remoteok" in remote_es  # but remote-first boards remain


def test_every_geo_source_renders_an_http_search_url_with_the_query() -> None:
    sources = registry.load_sources()
    for slug in _UK_SLUGS | _ES_SLUGS:
        src = sources[slug]
        url = src.search_url("data engineer")
        assert url.startswith("https://")
        assert "{query}" not in url  # the placeholder was filled
        # the exact quote_plus output landed in the URL (all geo boards are
        # query-param, so `+` is the correct space encoding)
        assert "data+engineer" in url


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
