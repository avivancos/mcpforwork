# Dedup engine — canonical URLs, hashes, check_seen

> The correctness core transplanted from startup-jobs-radar: canonical URL
> normalization, sha256 dedup hashing, the `external_applications` store, and
> `check_seen` — the gate every apply flow runs through so the copilot never
> touches the same opportunity twice without knowing. Built by S1.4; S2.4
> later extended `check_seen` across the scouted `explore_findings` table.

## How it works

**Canonicalization** (`src/mcpforwork/domain/urls.py:106`, a pure-stdlib leaf
— imports nothing but the standard library). Order matters:
1. parse; force scheme `https` (a scheme-less input is reparsed with an
   explicit prefix so the host lands in netloc);
2. lowercase netloc, strip leading `www.` (LinkedIn KEEPS `www.`), strip
   default ports `:443` / `:80`;
3. ATS-shape canonicalization BEFORE generic query handling — a matching
   (host, path) returns the minimal stable form immediately
   (`_canonical_ats`, :69-103): LinkedIn `/jobs/view/<id>/`, Greenhouse,
   Lever, Ashby (`/application/` and bare collapse equal), Workable,
   SmartRecruiters, Teamtailor (subdomain preserved);
4. otherwise: drop tracking params (the `_TRACKING_PARAMS` denylist :34 plus
   any `utm_` prefix — keys are lowercased before matching, so a case-only
   difference cannot change the hash), sort the remaining query params, strip
   the fragment, `path.rstrip('/') or '/'` lowercased;
5. `urlunparse` → the canonical string.

Idempotent: `canonical_url(canonical_url(u)) == canonical_url(u)`. Empty
input returns `""`; a host-less input (`/jobs/123`) is treated as opaque and
returned unchanged (:128-132).

**Hash** (`src/mcpforwork/domain/dedup.py:16`): `dedup_hash(url)` = sha256 of
the canonical URL — the cross-pipeline dedup key.

**Store** (migration 3: `adapters/db/migrations.py:97-113` for SQLite,
`adapters/db/pg/003_external_applications.sql` for Postgres):
`external_applications` records hand/external applies (LinkedIn Easy Apply,
apply-by-email, web forms) with `UNIQUE(user_id, dedup_hash)` — the
idempotence backbone. Per-user table → FORCE RLS on Postgres.

**Services** (`src/mcpforwork/services/dedup.py`) — `(uow, user_id, ...)`
signatures, the caller commits:
- `check_seen(uow, user_id, urls)` (:28) — looks each URL's hash up in BOTH
  `external_applications` and `explore_findings`; returns per-item `{seen,
  applied, discarded, status, source, finding_id, external_application_id,
  recommendation}` where `recommendation` is `skip` when already known and
  `new` otherwise, plus batch counts and the new/seen URL lists.
- `record_application(...)` (:89) — idempotent by `(user_id, dedup_hash)`: a
  second call UPDATEs the existing row (`deduped=True`) instead of inserting
  a duplicate. When `finding_id` is not given, a same-hash finding is
  auto-linked (:117-122) and flipped to the terminal `applied_external`
  status (:170-175). Writes an audit row. Does NOT commit.
- `recompute_hashes(uow, user_id)` (:189) — re-canonicalizes stored hashes
  after any `canonical_url` change; merges tracking-param duplicates (the
  lower id survives); idempotent on a second run.

## Design decisions

- **Pure stdlib by design** — zero dependencies is the point of the donor
  design; the leaf sits at the bottom of the domain import graph.
- **ATS hosts hardcoded in the domain leaf on purpose** (urls.py:50-51) — it
  must not import the packs layer.
- **Cut from the donor port** (S1.4): the `job_id`→`approve_job` delegation
  (the approve flow arrived in S3.4) and the company/title soft-dedup /
  `seen_companies` (the S2 findings pipeline). `record_application` takes
  explicit args and writes the dedup hash + audit row.
- **`finding_id` shipped as an unconstrained column** — S2's migration 4
  added the FK to `explore_findings` via the table-recreate pattern
  (migrations.py:115-120).

## Testing

- `tests/test_dedup_canonical.py` — LinkedIn dirty variants collapse to one
  canonical form and share one hash; generic dirty variants; every ATS shape
  (parametrized); idempotence; query-param sorting; mixed-case tracking
  params stripped like lowercase; relative URLs opaque; empty input;
  `dedup_hash` is sha256 of the canonical URL.
- `tests/test_dedup_seen.py` — unseen URL recommended `new`; blank URLs
  skipped; a recorded application is then seen + skipped; tracking-param
  variants match; idempotent record; URL required; audit row written;
  cross-user isolation; a scouted finding flagged seen; record links + flips
  a matching finding; recompute merges stale duplicates and is idempotent.
- `tests/test_dedup_rls_live.py` (live) — FORCE RLS on
  `external_applications` as the `app` role: cross-tenant invisibility,
  fail-closed unset context, idempotence and recompute-merge respect
  `UNIQUE(user_id, dedup_hash)` on Postgres.

## Gotchas

- **ATS canonicalization must run BEFORE generic query handling** — otherwise
  tracking junk survives on ATS URLs and the same posting hashes differently
  (urls.py:11-22).
- **LinkedIn keeps `www.`** in its canonical form while every other host
  strips it — LinkedIn is detected on the netloc that still carries `www`
  (:147-150).
- **Merge order in `recompute_hashes` matters**: delete the loser BEFORE
  updating the winner, or the winner trips `UNIQUE(user_id, dedup_hash)`
  (:224-236).
- **`check_seen` queries both tables** — a posting counts as `applied` when
  an external application exists OR the finding's status is
  `applied_external`; `discarded` findings are surfaced, not hidden (:53-63).
- **`record_application` does not commit** — the caller owns the transaction,
  so the audit row and the write land atomically inside the caller's unit of
  work.
