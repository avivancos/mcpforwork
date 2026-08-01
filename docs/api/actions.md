# Match actions + profile write API

> The dashboard's low-risk writes: `POST /v1/matches/{id}/approve|discard|
> restore|outcome` and `GET/POST /v1/profile`, each delegating to an existing
> service, with structured error kinds instead of substring sniffing. Built by
> S6.10 (error kinds + test gaps), S6.6b (routes + `restore_match`).

## How it works

**Routes** — `src/mcpforwork/entrypoints/api/app.py`, all behind `_authed`:

- `_match_action` (app.py:344) is the shared seam for approve/discard/restore:
  parse the path id (non-int → 404), call the service, map the result via
  `_action_response`, and commit ONLY on 204 (app.py:352-353).
- `_action_response` (app.py:338) maps structured error kinds to statuses via
  `_KIND_STATUS` (app.py:336): `not_found`→404, `invalid_state`→400,
  `invalid_input`→400, default 400. Success → 204 (the web's `call` maps 204 →
  undefined). NO substring matching on error messages.
- `POST /v1/matches/{id}/approve` → `review.approve_match`; `/discard`
  tolerates a missing/malformed body (`reason` defaults to "",
  app.py:359-367); `/restore` → `review.restore_match`.
- `POST /v1/matches/{id}/outcome` (app.py:372): validates the body, maps the
  WEB outcome vocabulary to the service vocabulary via `_WEB_OUTCOMES`
  (app.py:52 — `no_response`→`no_reply`; rejected/interview/offer pass
  through; unknown → 400 listing valid values), 404s when the finding is not
  the user's (`hunt.get_match`), resolves the finding's LATEST application
  (`ORDER BY id DESC LIMIT 1`, app.py:392-396; none → 400 "no application
  yet"), then delegates to `apply.record_outcome`.
- `GET /v1/profile` → `profiles.get_web_profile`; `POST /v1/profile` →
  `profiles.update_web_profile` (service `error` → 400, else 204).

**Services and their error kinds:**

- `services/review.py` — error dicts carry `kind` next to the human message
  (module docstring, review.py:1-5). `_not_found` (review.py:20) is the single
  helper (3 use sites — rule of two) so unknown and foreign matches stay
  indistinguishable BY CONSTRUCTION. `approve_match` (review.py:25) only from
  `new`/`review` (`_APPROVABLE`, review.py:17) with the state predicate inside
  the UPDATE itself (concurrent-safe; `rowcount == 0` → `invalid_state`),
  audited. `discard_match` (review.py:50) records the reason. `restore_match`
  (review.py:64) re-opens discarded → new with the same in-UPDATE status guard,
  audited.
- `services/apply.py::record_outcome` (apply.py:365): `invalid_input` for an
  outcome outside `OUTCOMES` (apply.py:283), `not_found` for an
  unknown/foreign application, `invalid_state` unless the application is
  `submitted`/`verified`; audited.
- `services/profiles.py` — web `Profile` shape mapping:
  - `get_web_profile` (profiles.py:274): a fresh user gets
    `_DEFAULT_WEB_PROFILE` (profiles.py:256, tier1Step 1); otherwise every
    field derives from real columns — name←full_name, email←contact_email,
    headline←career_narrative, targetRole←target_titles[0], cities←[city],
    workRights←work_auth_countries joined (+ "needs sponsorship"),
    salaryFloor←formatted min_salary_*, workMode←work_modes[0],
    languages←" · "-joined, seniority←seniority,
    employmentType←employment_types[0] via `_EMPLOYMENT_DISPLAY`
    (profiles.py:248), achievements/styleProfile from their child tables,
    tier1Step derived: tier-1 gaps open → 2, none → 4.
  - `update_web_profile` (profiles.py:314) maps the dashboard's
    `Partial<Profile>` onto intake columns: name→full_name,
    email→contact_email, headline→career_narrative, targetRole→target_titles
    (single-entry list, blank ignored), seniority→seniority LOWERCASED,
    employmentType→employment_types (display→enum; unknown display value →
    error), workMode→work_modes, languages→languages (split on "·"),
    cities→city (FIRST entry only — the intake model has no target-cities
    column; collapse documented). **Display-only fields with no column are
    ignored by design: workRights, salaryFloor, tier1Step** — never add schema
    for a display field. The profile is created on first save. Empty patch →
    `{"ok", changed: []}`.

**CI guard** — `.github/workflows/ci.yml:43-50` fails the build if
`"not found" in` appears under `src/mcpforwork/entrypoints/api/` — the
structural killer for the "revert to substring check" mutant, which is
behaviorally identical today and would survive test-only mutation.

## Design decisions

- **Kinds are additive** (S6.10): the MCP tools keep reading only `error`
  (message-only contract unbroken); `kind` is never read by the MCP
  entrypoint.
- **Unknown and foreign are indistinguishable** — both `not_found` → 404, by
  construction via `_not_found`, not by convention.
- **204 + commit-only-on-success**: the route commits the uow only when the
  service returned success, so a 400/404 leaves no partial writes.
- **Profile POST writes only existing columns** — a patch can never create
  schema; raw intake keys in the body (`full_name`, `label`,
  `min_salary_amount`) do NOT smuggle through because only the mapped web keys
  are read.

## Testing

`tests/test_match_actions_api.py` (TestClient, zero mocks, 20 tests):

- Auth required on all action routes; unknown/foreign → 404 for approve AND
  (S6.10 additions) discard/restore/outcome.
- approve status-guard; discard records the reason; restore only reopens
  discarded and (S6.10) writes an audit row.
- Outcome: web→service vocabulary mapping, unknown value → 400, no
  application → 400, application in `filling` → 400 via the API (S6.10 —
  invalid transition proven through the route, not just the service).
- Structured kinds asserted at the service level
  (`test_review_errors_carry_a_structured_kind`,
  `test_record_outcome_errors_carry_a_structured_kind`).
- Profile: fresh-user default shape, web-field→column mapping round-trip,
  invalid enum → 400, display-only fields create no schema, raw-intake-key
  anti-smuggling (S6.10).
- Cross-tenant 404s throughout (user A cannot act on user B's match).

## Gotchas

- The `restore_match`/`approve_match` concurrent-guard branch
  (`rowcount == 0`) is unreachable in single-thread tests — an accepted
  limitation recorded in writing on S6.6b (review P2); S6.10 kept it covered
  only transitively (gate P3, no action).
- Dashboard edits to `workRights`/`salaryFloor` return 204 but do NOT persist
  (no intake column) — a product note on S6.6b: a future card or the UI should
  communicate this.
- Patch semantics: empty strings and an empty `cities` list are no-ops —
  fields cannot be cleared via the dashboard patch; `seniority` is lowercased.
- `record_outcome`'s docstring does not restate the kind contract (the
  review.py module docstring does) — gate P3, noted, no action.
- The outcome route resolves the LATEST application per finding; an abandoned
  earlier application is never the target.
