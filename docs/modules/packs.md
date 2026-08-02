# Source packs (packs-as-data)

> Versioned YAML DATA that teaches the copilot HOW to search each job site —
> deployable independently of releases, sector/country logic as data not code
> (AGENTS.md §1.5). The schema + validator (S2.3), the browser-verified UK/ES
> geo packs (S2.5), and the `search_box` playbook mode for SPA/Cloudflare
> boards (S2.6). Cards (latest first): S2.6, S2.5, S2.3.

## How it works

**File shape.** `src/mcpforwork/packs/*.yaml`: a `pack` metadata block
(`id`, integer `version`, `kind: global|country|sector`) plus a `sources` list.
Each source declares `slug`, `name`, `base_url`, ISO-3166 alpha-2 `countries`
(or `global`), `sectors` (or `any`), `remote`, `tier: free|pro`, `enabled`, a
`search_playbook`, and an optional `apply_playbook` (`ats_hint`,
`auto_apply_safe`).

**Schema + validator.** `domain/packs.py` is PURE: `validate_pack(data) ->
list[str]` (`domain/packs.py:122-147`) returns human-readable errors (empty =
valid) — required fields, ISO-code shape (`_ISO_ALPHA2`, `:30`), unique slugs,
enum tiers/kinds, boolean flags. Security invariants: `base_url` and
`url_template` must be http(s) (`:64-65`, `:96-97`) because the URL is opened
in the user's browser; `url_template` mode requires a `{query}` placeholder
(`:101-102`).

**Two search modes** (`SEARCH_MODES`, `domain/packs.py:29`). `url_template`
(default): `{query}` is quote_plus-encoded into a navigable URL.
`search_box`: the template is a plain search PAGE and `result_hint` — required
to contain `{query}` in this mode (`:103-110`) — tells the client to type the
query into the board's on-page box. Absent `mode` defaults to `url_template`.

**Registry.** `packs/registry.py` loads every shipped pack at import time via
`load_sources()` (`registry.py:72-86`, `lru_cache(maxsize=1)`), validates each
(raising `PackError` on any error or cross-pack slug collision — a broken pack
never ships silently), and maps to the frozen `PackSource` dataclass
(`registry.py:29-51`). `PackSource.search_url(query)` (`:44-51`) fills the
template with `quote_plus` in `url_template` mode and returns the page
unchanged in `search_box` mode. `sources_for(countries, sectors, remote)`
(`registry.py:95-116`) selects enabled sources by tag overlap; `global`/`any`
tags match everything, `remote=True/False` filters on the remote flag, `None`
does not filter.

**Shipped packs (20 sources).** `global-remote.yaml` v2 — 5 remote boards, ALL
`search_box` (browser-verified S2.6: none have working URL-param search), with
a header comment documenting why `remoteok` (paywalled search) and `hnhiring`
(tag-index, no search box) are NOT shipped. `uk.yaml` (4: indeed-uk, reed,
adzuna-uk, linkedin-uk), `es.yaml` (5: infojobs, indeed-es, adzuna-es,
tecnoempleo, linkedin-es), `us.yaml` (3), `de.yaml` (3) — all `url_template`
mode, query-param style, browser-verified.

**Consumers.** `services/hunt.py` (`hunt_plan`, `source_playbook`,
`list_sources`) surfaces `mode` per source; the client-facing breadcrumbs and
the `/hunt` prompt branch on it (see `docs/modules/hunt.md`,
`docs/guidance.md`). Since S7.2b, `services/autopilot.py` reads
`apply_playbook.auto_apply_safe` via `safe_source_slugs()` — the flag now
GATES the L2 autopilot (policy evaluation + queue + the API's boards list);
no shipped pack is flagged yet (S7.2c curates which, after human browser
verification).

## Design decisions

- **YAML + `pyyaml`** so community packs are PR-friendly data contributions;
  the full 155-source donor migration is an ongoing PR task, deliberately NOT
  a mechanical port of the donor's free-text `cat`/`region` tags (S2.3
  simplicity gate).
- **Browser-verified URLs only** (S2.5/S2.6): every shipped `url_template`
  returned real listings in a real browser. Country aggregators
  (Indeed/Reed/Adzuna/InfoJobs/Tecnoempleo) are the verified workhorses;
  dedicated remote boards are SPAs/Cloudflare-gated → `search_box`.
- **ISO codes, not names**: `GB` not "UK"; the client LLM normalizes
  user-typed "UK" → `GB` at intake.
- **`apply_playbook` URL scheme validation deferred** to the S4 apply card
  (no live path when S2.3 shipped; ADR 0001).

## Testing

- `tests/test_packs.py` — validator unit cases (missing field, bad country,
  missing `{query}`, duplicate slug, unknown tier/kind, non-http template AND
  base_url, non-bool `auto_apply_safe`); every shipped pack loads + validates;
  `sources_for` selection incl. non-matching-sector exclusion.
- **Path-SEO guard** (`test_packs.py:113-126`): no shipped `url_template`-mode
  source may put `{query}` in the URL path — quote_plus encodes space as `+`,
  which path segments take literally. `search_box` sources are exempt.
- `search_box` mode tests (`test_packs.py:129-241`): hint required and must
  name `{query}`, scheme still checked, mode surfaced through `hunt_plan`/
  `source_playbook`, and a negative test pins `remoteok`/`hnhiring` as
  not-shipped.
- `tests/test_geo_packs.py` — GB/ES selection and cross-exclusion, remote
  filtering, and every geo source renders an http URL containing the exact
  `quote_plus` output (`data+engineer`).

## Gotchas

- **Path-SEO portals break quote_plus** (S2.5): Totaljobs/CV-Library were
  dropped and the pre-existing `stepstone-de` swapped for `adzuna-de` because a
  `{query}` in the URL PATH receives `+` literally. The structural guard test
  above is what makes this class unshippable — it also caught the broken
  RemoteOK tag-path.
- **RemoteOK is NOT a working free board** (S2.6 browser evidence): tag-path
  fails multi-word titles AND the on-page search hard-paywalls ($14.95/mo).
  Re-adding it would funnel users into a paywall; the negative test pins the
  decision.
- **A search-page template without `mode: search_box` fails validation** — the
  default `url_template` mode demands `{query}` in the URL, so the realistic
  authoring mistake fails loud instead of shipping a dead source
  (`test_packs.py:184-193`).
- **Surfacing `mode` is inert unless the client is told to branch on it** (S2.6
  gate P2): the breadcrumbs, `SERVER_INSTRUCTIONS`, and `/hunt` prompt all
  mention `search_box`, pinned by
  `test_hunt_guidance_tells_the_client_to_use_the_search_box_when_mode_says_so`.
- **`load_sources` is `lru_cache`d** — tests that write pack files must not
  assume a re-read within one process.
- **Flagging `auto_apply_safe: true` is a consent-relevant act** (S7.2b): the
  moment a pack ships it, L2 policies can authorize submits on that board
  without per-application approval. S7.2c sets it ONLY after human browser
  verification of a native, login-free, non-hostile apply flow — expect few;
  that conservatism is the product's risk posture.
- **Open P3s (carded for the community-pack ingestion sprint):** `result_hint`
  is client-facing untrusted text (injection-shaped content is possible) and an
  unhashable `mode` value raises `TypeError` instead of a validation error.
