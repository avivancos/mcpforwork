# Profiles — intake model, achievements bank, style profile

> The `profiles` data model (Tier 1 required intake, Tier 2 progressive
> fields), the achievements bank, and the per-profile style profile, plus the
> profile services every surface wraps. Built by S1.3; later extended by S5.2
> (`profile_gaps` progressive Tier 2) and S6.6b (web dashboard mapping).

## How it works

**Schema** (migration 2: `adapters/db/migrations.py:36-90` for SQLite,
`adapters/db/pg/002_profiles.sql` for Postgres — per-user tables, FORCE-RLS
on PG):
- `profiles` — Tier 1: `full_name`, `contact_email`, `country`, `city`,
  `work_auth_countries`, `needs_sponsorship`, `target_titles` (1–5),
  `sectors`, `seniority`, `employment_types`, `work_modes`, `relocation`,
  `min_salary_{amount,currency,period}` (PRIVATE), `languages`, `cv_text`.
  Tier 2 (nullable): `links`, `availability_date`, `notice_period`,
  `deal_breakers`, `career_narrative`, `salary_public_*`,
  `negotiation_floor`. Plus `label` + `is_active` for multi-profile support.
- `achievements` — the quantified-wins bank (`metric` required, `context`,
  `role`), FK to `profiles`.
- `style_profile` — one per profile (`UNIQUE(profile_id)`): `writing_sample`
  + derived `directives` (JSON).

List/dict fields are JSON-text columns; the service (de)serializes them at
the boundary (`services/profiles.py:19-28`).

**Domain** (`src/mcpforwork/domain/profile.py`, pure): enums `Seniority`,
`EmploymentType`, `WorkMode`, `SalaryPeriod`; `MAX_TARGET_TITLES = 5` (:14);
`JSON_FIELDS` / `SCALAR_FIELDS` / `EDITABLE_FIELDS` (:55-89);
`PRIVATE_SALARY_FIELDS` (:48-52); `validate_patch` (:106) rejects unknown
fields, enum violations, and more than 5 target titles. The intake model is
sector- and country-agnostic BY DATA — titles and sectors are user-supplied
values, never hardcoded personas.

**Services** (`src/mcpforwork/services/profiles.py`) — `(uow, user_id, ...)`
signatures, the caller commits, every query scoped by `user_id`:
- `create_profile` (:41) — validates the payload, deactivates the previously
  active profile first (one active profile per user), returns the new id.
- `get_profile` (:70) / `list_profiles` (:82) — the active profile by
  default; JSON fields parsed into plain Python.
- `update_profile` (:87) — validated partial patch; unknown fields rejected.
- `set_active_profile` (:106) — switches the active flag atomically.
- `add_achievements` (:113) / `list_achievements` (:132) — `metric` required.
- `set_style_profile` (:139) / `get_style_profile` (:166) — upsert, one per
  profile.
- `export_for_brief` (:220) — profile facts destined for a generation brief;
  `min_salary_*` redacted unless `disclose_salary=True` — the structural
  privacy gate (the client LLM never sees private deal-breaker figures
  without explicit consent).
- `profile_gaps` (:201, S5.2) — missing fields tier-1-first from
  `_GAP_CATALOGUE` (:181); the progressive `/setup` data.
- `get_web_profile` / `update_web_profile` (:274 / :314, S6.6b) — the
  dashboard `Profile` shape mapped onto intake columns (creating the profile
  on first save).

`_require_owned_profile` (:31) rejects writes targeting a profile the user
does not own, so a child row (achievement, style) can never be stamped onto
a foreign profile.

## Design decisions

- **JSON-text columns, not child tables** — no query needs per-title or
  per-language rows yet; revisit if scoring ever does (S1.3 improvements).
- **Privacy gate encoded at the service boundary**: only `min_salary_*` is
  never-disclose-by-default; `salary_public_*` and `negotiation_floor` are
  offer-stage figures the candidate opted to share, so they pass through
  (:234-240). EEO data would be gated here too once stored.
- **Deferred (YAGNI, S1.3 improvements)**: `star_stories` (consumer is
  `/interview`) and EEO/demographics (needs the hosted encryption-at-rest key
  story). The privacy gate that would protect EEO is already in place.
- **Stdlib validation, no pydantic** — the charter requires a justification
  line per new dependency; none was needed.
- **Display-only fields get no schema** — `update_web_profile` ignores
  `workRights` / `salaryFloor` / `tier1Step` by design (:316-318).

## Testing

- `tests/test_profiles.py` — Tier 1 round-trip; invalid seniority, >5 titles,
  and unknown fields rejected; a second active profile deactivates the first;
  achievements append + metric required; style upsert; salary redacted by
  default and disclosed only with consent; cross-user read/write rejected.
- `tests/test_profiles_rls_live.py` (live) — FORCE RLS on the real tables as
  the `app` role: cross-tenant invisibility, fail-closed unset context.
- `tests/test_profile_gaps.py` — the S5.2 gap-catalogue behavior.

## Gotchas

- **`label` is not settable via the data map** — `create_profile` pops it and
  sets it explicitly (:53).
- **An empty patch is a no-op**, but still validated first (:92-94).
- **`style_profile` is upserted**, keyed by `UNIQUE(profile_id)` — one per
  profile, not one per user.
- **Gap checks for `achievements` / `style_profile` query the child tables**,
  not profile columns (:209-212).
- **The web `cities` list collapses to the single `city` column** — the
  intake model has no target-cities column (:339-342).
