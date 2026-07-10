"""Canonical URL normalisation — the single source of truth for dedup keys.

Ported verbatim (behavior-preserving) from startup-jobs-radar's hardest-won
correctness. All URL variants of one posting must collapse to ONE canonical
string so the same job hashes identically regardless of tracking params,
scheme, ``www.``, or trailing slash.

Pure stdlib leaf — imports nothing but the standard library, so it sits at the
bottom of the domain import graph.

Normalisation order (ATS-shape canonicalisation happens BEFORE generic query
handling so ATS job URLs reduce to their minimal stable form regardless of
tracking junk):

1. parse
2. force scheme ``https``
3. lowercase netloc + strip leading ``www.`` (LinkedIn keeps ``www.``)
4. strip default port (``:443``/``:80``)
5. ATS-shape canonicalisation -> minimal form, return immediately on match
6. else: drop tracking params (denylist + ``utm_`` prefix), sort remaining,
   strip fragment, ``path.rstrip('/') or '/'``
7. ``urlunparse`` -> final string
"""

from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

# Exact tracking-param keys dropped from non-ATS URLs (in addition to the
# ``utm_`` prefix). Members are LOWERCASE: the match lowercases each incoming
# key, so mixed/upper-case variants are stripped like their lowercase forms — a
# case-only difference must not produce a different dedup hash.
_TRACKING_PARAMS: frozenset[str] = frozenset(
    {
        "ebp",
        "refid",
        "trackingid",
        "trk",
        "gh_src",
        "src",
        "ref",
        "lipi",
        "originalsubdomain",
        "position",
        "pagenum",
    }
)

# ATS host/path patterns -> minimal canonical form. Hosts are hardcoded here on
# purpose — this leaf must not import the packs layer.
_LINKEDIN_NETLOC = re.compile(r"^(www\.)?linkedin\.com$")
_LINKEDIN_PATH = re.compile(r"^/jobs/view/(\d+)")
_GREENHOUSE_NETLOC = re.compile(r"^boards\.greenhouse\.io$")
_GREENHOUSE_PATH = re.compile(r"^/([^/]+)/jobs/(\d+)")
_LEVER_NETLOC = re.compile(r"^jobs\.lever\.co$")
_LEVER_PATH = re.compile(r"^/([^/]+)/([a-f0-9-]+)")
_ASHBY_NETLOC = re.compile(r"^jobs\.ashbyhq\.com$")
_ASHBY_PATH_APP = re.compile(r"^/([^/]+)/application/([a-f0-9-]+)")
_ASHBY_PATH = re.compile(r"^/([^/]+)/([a-f0-9-]+)")
_WORKABLE_NETLOC = re.compile(r"^apply\.workable\.com$")
_WORKABLE_PATH = re.compile(r"^/([^/]+)/j/([^/]+)")
_SMARTRECRUITERS_NETLOC = re.compile(r"^jobs\.smartrecruiters\.com$")
_SMARTRECRUITERS_PATH = re.compile(r"^/([^/]+)/(\d+)")
_TEAMTAILOR_NETLOC = re.compile(r"^([^.]+)\.teamtailor\.com$")
_TEAMTAILOR_PATH = re.compile(r"^/jobs/(\d+)")


def _canonical_ats(netloc: str, path: str) -> str | None:
    """Return the minimal canonical ATS URL when (netloc, path) matches a known
    ATS shape. ``netloc`` is already lowercased + de-``www``'d by the caller
    EXCEPT LinkedIn, which is detected here so the canonical ``www.linkedin.com``
    is preserved."""
    if _LINKEDIN_NETLOC.match(netloc):
        m = _LINKEDIN_PATH.match(path)
        if m:
            return f"https://www.linkedin.com/jobs/view/{m.group(1)}/"
    if _GREENHOUSE_NETLOC.match(netloc):
        m = _GREENHOUSE_PATH.match(path)
        if m:
            return f"https://boards.greenhouse.io/{m.group(1)}/jobs/{m.group(2)}"
    if _LEVER_NETLOC.match(netloc):
        m = _LEVER_PATH.match(path)
        if m:
            return f"https://jobs.lever.co/{m.group(1)}/{m.group(2)}"
    if _ASHBY_NETLOC.match(netloc):
        m = _ASHBY_PATH_APP.match(path) or _ASHBY_PATH.match(path)
        if m:
            return f"https://jobs.ashbyhq.com/{m.group(1)}/{m.group(2)}"
    if _WORKABLE_NETLOC.match(netloc):
        m = _WORKABLE_PATH.match(path)
        if m:
            return f"https://apply.workable.com/{m.group(1)}/j/{m.group(2)}"
    if _SMARTRECRUITERS_NETLOC.match(netloc):
        m = _SMARTRECRUITERS_PATH.match(path)
        if m:
            return f"https://jobs.smartrecruiters.com/{m.group(1)}/{m.group(2)}"
    tt = _TEAMTAILOR_NETLOC.match(netloc)
    if tt:
        m = _TEAMTAILOR_PATH.match(path)
        if m:
            return f"https://{tt.group(1)}.teamtailor.com/jobs/{m.group(1)}"
    return None


def canonical_url(raw: str) -> str:
    """Return a canonical, dedup-stable form of ``raw``.

    Idempotent: ``canonical_url(canonical_url(u)) == canonical_url(u)`` for
    every URL. Empty / falsy input returns ``""``.
    """
    if not raw:
        return ""
    raw = raw.strip()
    if not raw:
        return ""

    parsed = urlparse(raw)

    # Force https. http -> https; a scheme-less input (``example.com/x``) is
    # reparsed with an explicit prefix so the host lands in netloc, not path.
    if parsed.scheme in ("", "http"):
        if parsed.scheme == "":
            parsed = urlparse("https://" + raw)
        else:
            parsed = parsed._replace(scheme="https")

    # A no-host input like ``/jobs/123`` reparses to ``https:///jobs/123`` (empty
    # netloc) — that is not a dedupable URL, so return the stripped input
    # unchanged (treat as opaque). A real scheme-less host is unaffected.
    if not parsed.netloc:
        return raw

    netloc = parsed.netloc.lower()
    stripped_netloc = netloc[4:] if netloc.startswith("www.") else netloc

    def _strip_default_port(host: str) -> str:
        if host.endswith(":443"):
            return host[: -len(":443")]
        if host.endswith(":80"):
            return host[: -len(":80")]
        return host

    netloc = _strip_default_port(netloc)
    stripped_netloc = _strip_default_port(stripped_netloc)

    # ATS-shape canonicalisation (BEFORE query handling). Detect on the
    # lowercased+port-stripped netloc that still carries www (so LinkedIn's www
    # is visible); return the minimal form on match.
    ats = _canonical_ats(netloc, parsed.path)
    if ats is not None:
        return ats

    # Generic non-ATS URL: drop tracking params, sort the rest, strip fragment,
    # normalise path.
    pairs = parse_qsl(parsed.query, keep_blank_values=False)
    kept = [
        (k, v)
        for (k, v) in pairs
        if k.lower() not in _TRACKING_PARAMS and not k.lower().startswith("utm_")
    ]
    kept.sort(key=lambda kv: kv[0])
    query = urlencode(kept)

    # Lowercase the path for non-ATS URLs so generic job URLs differing only in
    # path case collapse to one hash. ATS shapes are unaffected — they returned
    # early with a regex-rebuilt canonical form.
    path = (parsed.path.rstrip("/") or "/").lower()

    return urlunparse(("https", stripped_netloc, path, "", query, ""))
