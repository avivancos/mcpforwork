# Autopilot policy API (L2)

> The HTTP surface of the L2 autopilot policy: `GET`/`PUT /v1/autopilot/policy`,
> `POST /v1/autopilot/policy/revoke`, `GET /v1/autopilot/boards`. PUT/revoke are
> CONSENT WRITES (ADR 0005, §9 P0) — session-authenticated, the ONLY place a
> policy is minted or revoked; the MCP entrypoint has read-only tools instead.
> Built by S7.2b (routes + service); W6.3 added the boards route and mapped the
> GET seam to camelCase. Service module: `docs/modules/autopilot.md`; the web
> consumer: `docs/modules/web.md` (Account → Autopilot).

## How it works

**Routes** — `src/mcpforwork/entrypoints/api/app.py`, all behind `_authed`
(401 without a live session), all auth-first (the P3-fixed posture of their
siblings):

- `GET /v1/autopilot/policy` (app.py:403, route :629) →
  `{"policy": <camelCase> | null}` — the active policy (newest non-revoked
  row) or null when autopilot is off. `_policy_json` (app.py:391) maps the
  service row to the web seam: `{enabled, minScore, maxPerDay, createdAt,
  revokedAt}`, coercing `enabled` with `bool()` (SQLite returns 0/1 for the
  INTEGER column, Postgres a real bool).
- `PUT /v1/autopilot/policy` (app.py:409, route :630) — mint/supersede. Body
  must be a JSON object with integer `min_score`/`max_per_day` (route-level
  type check, app.py:418-423; anything else → 400), then
  `autopilot.put_policy` revalidates ranges (0–100 / 1–50) and rejects JSON
  booleans. Commits only on 204 (`_action_response` maps service error kinds
  — S6.10).
- `POST /v1/autopilot/policy/revoke` (app.py:433, route :631) — revoke the
  active policy (204); none active → the service's `not_found` kind. Commits
  only on 204.
- `GET /v1/autopilot/boards` (app.py:442, route :632) →
  `{"boards": [{slug, name}]}` — packs-registry names for
  `autopilot.safe_source_slugs()`, `sorted()` for stable output (W6.3 gate
  P3). Honestly EMPTY until S7.2c human-verifies a board and flags its pack
  `auto_apply_safe` — the dashboard renders its empty state, never a
  fabricated board.

## Design decisions

- **Asymmetric wire shape (W6.3).** GET returns camelCase — the web seam is
  camelCase end-to-end (the PipelineItem precedent) — while PUT accepts
  snake_case (`min_score`/`max_per_day`, mirroring the service kwargs); the
  web HTTP adapter maps at the boundary (`web/src/lib/api/http.ts:67-68`).
  The camelCase GET is pinned by `test_policy_routes_roundtrip`.
- **Commit-on-204 only**: a service error kind must not persist the
  supersede's prior-row revocation — the route commits the UoW exclusively
  on success.
- **Boards come from packs data, never hardcoded in the web app** (invariant
  §1.5): the route reads the registry at request time, so a pack release
  flagging a board safe needs no web/API deploy.
- **Consent writes stay off the MCP surface**: the CI consent-write gate
  (`ci.yml:43-57`) fails the build on `INSERT INTO/UPDATE autopilot_policy`
  outside `services/autopilot.py`; these two routes are that module's only
  callers.

## Testing

Route tests live in `tests/test_autopilot_l2.py` (TestClient, real SQLite,
zero mocks):

- `test_policy_routes_require_a_session` (:496) — 401 matrix over all four
  routes, boards included (W6.3 mutant probe: dropping the boards auth check
  fails this test).
- `test_policy_routes_roundtrip` (:519) — PUT 204 → GET camelCase
  (`minScore`/`maxPerDay`/`revokedAt`/`createdAt`/`enabled`) → revoke 204 →
  GET `policy: null`. The camelCase pin is the W6.3 mutant probe (dropping
  `_policy_json` mapping → KeyError).
- `test_put_policy_route_validates_the_body` (:540) — non-dict, missing, and
  non-integer bodies all 400.
- `test_policy_routes_never_leak_across_tenants` (:571) — one user's policy
  is invisible/unrevocable to another.
- `test_boards_route_lists_only_flagged_safe_sources` (:507) — today:
  `{"boards": []}`.

## Gotchas

- **`enabled` crosses the seam as a real JSON bool** thanks to the `bool()`
  coercion in `_policy_json` — without it SQLite would leak `1`/`0` and the
  fixtures/real adapters would diverge in shape.
- **JSON booleans are not integers** — `isinstance(True, int)` is True, so
  both the route (`isinstance(x, int)` plus the service's explicit bool
  guard) reject `true` as a score/cap; unguarded, SQLite would store 1 and
  psycopg would 500 (S7.2b gate P3 fix).
- **Revocation is not retroactive** — already-minted L2 authorizations are
  not recalled (see `modules/apply.md`); the dashboard's revoke copy says so
  honestly.
- **The boards list is empty in production today** — by design, until S7.2c;
  do not "fix" the empty state by seeding a board.
