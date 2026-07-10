"""Canonical URL normalisation + dedup hash (ported from startup-jobs-radar).

All URL variants of one posting collapse to ONE canonical string and therefore
one dedup hash: LinkedIn tracking params, www/no-www, http->https, utm_*,
trailing slash. ATS shapes reduce to their minimal form. Pure stdlib leaf, so
these are direct value assertions — no mocks.
"""

import hashlib

import pytest

from mcpforwork.domain.dedup import dedup_hash
from mcpforwork.domain.urls import canonical_url

_LINKEDIN_CANON = "https://www.linkedin.com/jobs/view/123/"
_LINKEDIN_VARIANTS = [
    "https://www.linkedin.com/jobs/view/123/?eBP=x&refId=y&trackingId=z",
    "https://linkedin.com/jobs/view/123",
    "http://www.linkedin.com/jobs/view/123/",
    "https://www.linkedin.com/jobs/view/123/?utm_source=foo&utm_medium=bar",
    "https://www.linkedin.com/jobs/view/123",
    "https://www.linkedin.com/jobs/view/123/?trk=public_jobs&lipi=abc&position=4&pageNum=2",
]


@pytest.mark.parametrize("variant", _LINKEDIN_VARIANTS)
def test_linkedin_dirty_variants_collapse_to_one_canonical(variant: str) -> None:
    assert canonical_url(variant) == _LINKEDIN_CANON


def test_linkedin_dirty_variants_share_one_dedup_hash() -> None:
    hashes = {dedup_hash(v) for v in _LINKEDIN_VARIANTS}
    assert len(hashes) == 1


_GENERIC_CANON = "https://example.com/jobs/77"
_GENERIC_VARIANTS = [
    "http://www.example.com/jobs/77/",
    "https://example.com/jobs/77?utm_source=hn&ref=abc",
    "https://example.com/jobs/77/#section",
    "https://EXAMPLE.com/Jobs/77",
    "https://example.com:443/jobs/77",
    "https://example.com/jobs/77?src=newsletter&gh_src=x",
]


@pytest.mark.parametrize("variant", _GENERIC_VARIANTS)
def test_generic_dirty_variants_collapse(variant: str) -> None:
    assert canonical_url(variant) == _GENERIC_CANON


@pytest.mark.parametrize(
    "raw,expected",
    [
        (
            "https://boards.greenhouse.io/acme/jobs/4567?gh_src=abc&t=1",
            "https://boards.greenhouse.io/acme/jobs/4567",
        ),
        (
            "https://jobs.lever.co/acme/abc12345-6789-def0-1234-567890abcdef?lever-source=x",
            "https://jobs.lever.co/acme/abc12345-6789-def0-1234-567890abcdef",
        ),
        (
            "https://jobs.ashbyhq.com/acme/application/abc12345-6789-def0-1234-567890abcdef",
            "https://jobs.ashbyhq.com/acme/abc12345-6789-def0-1234-567890abcdef",
        ),
        (
            "https://apply.workable.com/acme/j/ABCDEF1234/?utm_source=x",
            "https://apply.workable.com/acme/j/ABCDEF1234",
        ),
        (
            "https://jobs.smartrecruiters.com/acme/74099999?trackingId=z",
            "https://jobs.smartrecruiters.com/acme/74099999",
        ),
        (
            "https://acme.teamtailor.com/jobs/55555?utm_medium=x",
            "https://acme.teamtailor.com/jobs/55555",
        ),
    ],
)
def test_ats_shapes_collapse_to_minimal_form(raw: str, expected: str) -> None:
    assert canonical_url(raw) == expected


def test_ashby_application_and_bare_collapse_equal() -> None:
    app_form = "https://jobs.ashbyhq.com/acme/application/abc12345-6789-def0-1234-567890abcdef"
    bare = "https://jobs.ashbyhq.com/acme/abc12345-6789-def0-1234-567890abcdef"
    assert canonical_url(app_form) == canonical_url(bare)


@pytest.mark.parametrize(
    "clean",
    [
        _GENERIC_CANON,
        _LINKEDIN_CANON,
        "https://boards.greenhouse.io/acme/jobs/4567",
        "https://jobs.lever.co/acme/abc12345-6789-def0-1234-567890abcdef",
    ],
)
def test_clean_url_roundtrip_is_noop(clean: str) -> None:
    assert canonical_url(clean) == clean


@pytest.mark.parametrize(
    "url", [*_LINKEDIN_VARIANTS, *_GENERIC_VARIANTS, _GENERIC_CANON, _LINKEDIN_CANON]
)
def test_canonical_url_is_idempotent(url: str) -> None:
    once = canonical_url(url)
    assert canonical_url(once) == once


def test_query_params_sorted_alphabetically() -> None:
    assert canonical_url("https://example.com/s?b=2&a=1&c=3") == "https://example.com/s?a=1&b=2&c=3"


def test_only_tracking_params_dropped_real_params_kept() -> None:
    out = canonical_url("https://example.com/s?q=python&utm_source=x&refId=y&page=2")
    assert out == "https://example.com/s?page=2&q=python"


def test_mixed_case_tracking_params_stripped_like_lowercase() -> None:
    dirty = "https://example.com/jobs/77?UTM_Source=x&RefID=y&TrackingId=z"
    assert canonical_url(dirty) == _GENERIC_CANON


@pytest.mark.parametrize("relative", ["/jobs/123", "/jobs/123?utm_source=x", "/a/b/c", "/"])
def test_relative_url_not_malformed(relative: str) -> None:
    out = canonical_url(relative)
    assert "https:///" not in out
    assert out == relative


@pytest.mark.parametrize("value", ["", "   "])
def test_empty_input_returns_empty(value: str) -> None:
    assert canonical_url(value) == ""


def test_dedup_hash_is_sha256_of_canonical() -> None:
    url = "http://www.example.com/jobs/77/?utm_source=x"
    assert dedup_hash(url) == hashlib.sha256(_GENERIC_CANON.encode()).hexdigest()
