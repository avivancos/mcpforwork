# Source packs (packs-as-data)

> Versioned YAML DATA that teaches the copilot HOW to search (and apply on)
> each job site — deployable independently of releases; sector/country logic
> as data not code (AGENTS.md §1.5). Schema + validator (S2.3), browser-verified
> UK/ES geo packs (S2.5), `search_box` mode for SPA/Cloudflare boards (S2.6),
> and curated `apply_playbook` + honest-empty `auto_apply_safe` (S7.2c).
> Cards (latest first): S7.2c, S2.6, S2.5, S2.3.

## How it works

**File shape.** `src/mcpforwork/packs/*.yaml`: a `pack` metadata block
(`id`, integer `version`, `kind: global|country|sector`) plus a `sources` list.
Each source declares `slug`, `name`, `base_url`, ISO-3166 alpha-2 `countries`
(or `global`), `sectors` (or `any`), `remote`, `tier: free|pro`, `enabled`, a
`search_playbook`, and an optional `apply_playbook`.

**`apply_playbook` contract** (`domain/packs.py` `_APPLY_PLAYBOOK_KEYS` /
`_validate_apply_playbook`, `:46-74`). Optional mapping; when present, only
these keys are allowed (unknown keys → validation error):

| Key | Type | Notes |
|-----|------|--------|
| `ats_hint` | `str` | Short classifier for clients / hunt `apply_hint` |
| `quirks` | `list[str]` | Injected into the fill plan as an `answer` step |
| `form_url_pattern` | `str` | Must start with `https://` (http / javascript / data rejected) |
| `auto_apply_safe` | `bool` | Consent-relevant: gates L2 via `safe_source_slugs()` |

Absence of the whole playbook = L0 apply behavior unchanged (no quirks step,
source not L2-eligible). `form_url_pattern` scheme validation closes the
[ADR 0001](../../backlog/decisions/0001_bootstrap_decisions.md) follow-up —
load-bearing now that clients open these URLs.

**Schema + validator.** `domain/packs.py` is PURE: `validate_pack(data) ->
list[str]` (empty = valid) — required fields, ISO shape (`_ISO_ALPHA2`),
unique slugs, enum tiers/kinds, boolean flags. Security: `base_url` and
`url_template` must be http(s); `url_template` mode requires `{query}`.

**Two search modes** (`SEARCH_MODES`, `:29`). `url_template` (default):
`{query}` is quote_plus-encoded into a navigable URL. `search_box`: the
template is a plain search PAGE and `result_hint` — required to contain
`{query}` in this mode (`:134-141`) — tells the client to type into the
on-page box. Absent `mode` defaults to `url_template`.

**Registry.** `packs/registry.py` loads every shipped pack at import via
`load_sources()` (`:72-86`, `lru_cache(maxsize=1)`), validates each (raises
`PackError` on error or cross-pack slug collision), maps to frozen
`PackSource` (`:29-51`). `PackSource.apply` holds the raw `apply_playbook`
dict (or `{}`). `search_url(query)` (`:44-51`) fills the template in
`url_template` mode; returns the page unchanged in `search_box`.
`sources_for(countries, sectors, remote)` (`:95-116`) selects enabled
sources by tag overlap (`global`/`any` wildcards; `remote` filters).

**Shipped packs (20 sources).** `global-remote.yaml` **v3** — 5 remote
boards, ALL `search_box` (S2.6), each with an `apply_playbook`
(`auto_apply_safe: false` + quirks/`ats_hint` from the S7.2c browser pass).
Header comments document why `remoteok` / `hnhiring` are NOT shipped.
`uk.yaml` (4), `es.yaml` (5), `us.yaml` (3), `de.yaml` (3) —
`url_template` mode; no apply playbooks yet (aggregators exit to employer
ATS; not L2 candidates without per-ATS work).

**Consumers.** `hunt_plan` surfaces `apply_hint` (= `ats_hint`);
`source_playbook` returns the full `apply_playbook`. `start_application`
loads `PackSource.apply` into `build_steps`, which appends an `answer` step
when `quirks` is non-empty (`domain/apply_flow.py:87-96`). The `/apply`
prompt (`server.py`) tells the client to honor those quirks.
`services/autopilot.safe_source_slugs()` reads `auto_apply_safe` — **S7.2c
result: allowlist stays empty** (`frozenset()`). Browser evidence (all FAIL
for L2): Remotive Unlock paywall; WWR Apply→account register; Working Nomads
→ external Breezy; Himalayas/Jobicy Cloudflare. Card:
`backlog/done/S7.2c_apply_playbook_packs.md`.

## Design decisions

- **YAML + `pyyaml`** so community packs are PR-friendly; the full donor
  migration is an ongoing PR task, not a mechanical port of free-text tags
  (S2.3 simplicity gate).
- **Browser-verified URLs only** (S2.5/S2.6/S7.2c): search templates and
  `auto_apply_safe: true` both require human evidence. Conservatism on the
  L2 flag is the product's risk posture — zero flagged after S7.2c is
  correct, not incomplete.
- **ISO codes, not names**: `GB` not "UK"; the client LLM normalizes at intake.
- **Unknown `apply_playbook` keys rejected** so pack drift fails loudly
  rather than being silently ignored by clients that open URL fields.

## Testing

- `tests/test_packs.py` — validator (missing field, bad country, missing
  `{query}`, duplicate slug, unknown tier/kind, non-http template/base_url,
  non-bool `auto_apply_safe`, apply_playbook unknown keys + https scheme +
  `ats_hint`/`quirks` types, allowlist guard
  `test_no_shipped_source_is_auto_apply_safe_without_evidence` with
  `allowed: frozenset()`, global-remote playbooks ship `safe: false` with
  non-empty quirks/`ats_hint`); every shipped pack loads; `sources_for`.
- **Path-SEO guard** (`test_packs.py`): no `url_template`-mode source may put
  `{query}` in the URL path — quote_plus's `+` breaks path segments.
  `search_box` exempt.
- `search_box` mode tests: hint required + `{query}`, scheme still checked,
  mode through `hunt_plan`/`source_playbook`, negative pin that
  `remoteok`/`hnhiring` are not shipped.
- `tests/test_geo_packs.py` — GB/ES selection, remote filter, URL rendering.
- `tests/test_mcp_server.py` — `/apply` prompt mentions apply_playbook /
  fill-plan quirks (S7.2c).

## Gotchas

- **Path-SEO portals break quote_plus** (S2.5): structural guard makes this
  class unshippable (also caught RemoteOK's tag-path).
- **RemoteOK is NOT a working free board** (S2.6): tag-path + hard paywall;
  negative test pins the decision.
- **A search-page template without `mode: search_box` fails validation** —
  default `url_template` demands `{query}` in the URL.
- **Surfacing `mode` is inert unless the client branches on it** (S2.6):
  breadcrumbs / `SERVER_INSTRUCTIONS` / `/hunt` mention `search_box`.
- **`load_sources` is `lru_cache`d** — pack-file tests must not assume a
  re-read within one process.
- **Flagging `auto_apply_safe: true` is consent-relevant** (S7.2b/c): L2
  policies can then authorize submits on that board without per-app approval.
  Re-curate only with a new card + browser evidence; do not invent boards
  to "fix" empty L2 queue / boards list.
- **Open P3s (community-pack sprint):** `result_hint` is untrusted
  client-facing text; an unhashable `mode` raises `TypeError` instead of a
  validation error.
