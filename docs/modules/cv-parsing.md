# CV parsing & progressive onboarding (parse_cv + profile_gaps)

> The zero-LLM onboarding extraction path: `domain/cv.py` parses pasted CV text
> into high-confidence contact fields plus evidence-only `setup_hints` (never
> inventing), the `parse_cv` MCP tool returns them for human CONFIRMation, and
> `profile_gaps` drives progressive Tier-2 profile completion during CV-first
> `/setup`. Cards (latest first): S5.3, S5.2, S5.1.

## How it works

**Parser.** `extract_profile_from_cv(cv_text)` (`src/mcpforwork/domain/cv.py:220`)
is pure stdlib regex, no I/O. Returns
`{candidate: {full_name, contact_email, phone, linkedin, github, portfolio},
setup_hints: {work_modes, employment_types, skills_top, signals}, cv_text}`;
any low-confidence contact field is `None`, and every hints list is `[]` when
unknown — the client asks the human instead of inventing.

- `_header_block` (`cv.py:138`) bounds name/phone extraction to the leading
  lines before the first section header (max 12 non-blank), so an EXPERIENCE
  title can never be mis-extracted as the candidate's name.
- `_extract_name` (`cv.py:152`): an explicit `Name:` label wins; otherwise the
  first header line that is not an email/URL/section header, not a bare field
  label (trailing `:`), not phone-like (>=7 digits), and not a sentence (>5
  words). Anything ambiguous -> `None`.
- Email is scanned over the whole document (`cv.py:224`) — contact info often
  sits at the bottom. Phone is header-only and needs >=9 digits (`cv.py:225-234`),
  which rejects date ranges like `2020-2023` (8 digits).
- LinkedIn/GitHub are matched by dedicated regexes; `portfolio` is the first
  remaining URL (`cv.py:236-244`). All values are trailing-punctuation stripped.

**setup_hints (S5.3).** `_extract_setup_hints` (`cv.py:174`) is evidence-only:

- `work_modes` / `employment_types` map keyword hits onto existing
  `WorkMode` / `EmploymentType` enums (`domain/profile.py`) — remote/hybrid/
  onsite; contract/freelance/full_time/part_time. Each hit also appends a
  `keyword: …` entry to `signals`.
- B2B / invoice are **signals only** (`cv.py:48-52`) — never coerced into
  `employment_types`.
- `skills_top`: frozen allowlist (`_SKILL_ALLOWLIST`, ~60 tokens), whole-word
  frequency, aliases normalized (e.g. `llms`→`llm`, `k8s`→`kubernetes`), top 12
  by count desc then name. Allowlist misses never appear.
- Empty CV / no modality / no allowlisted skills → all four lists `[]`. The
  server never invents titles, seniority, country, or salary.

**Tool.** `parse_cv` (`src/mcpforwork/entrypoints/mcp/server.py:607`) rejects
input over `MAX_CV_CHARS` (200_000, `cv.py:26`), returns the extraction, and
never writes the profile. Its `next_action` (`entrypoints/mcp/guidance.py:52`)
instructs: CONFIRM contact + review hints; the **client LLM** proposes
titles/seniority/sectors from `cv_text` + hints; CONFIRM focus; then
`update_profile` with confirmed values + `cv_text`. The `/setup` prompt is
CV-first (paste → `parse_cv` → confirm → persist → Tier 2) —
`server.py:645-668`.

**Progressive Tier 2.** `profile_gaps(uow, user_id)`
(`src/mcpforwork/services/profiles.py:201`) walks `_GAP_CATALOGUE`
(`profiles.py:181-198`) — `(field, tier, why)` tuples: tier 1 = required
intake, tier 2 = progressive unlocks (achievements bank first, then style
sample, links, deal_breakers, availability). `achievements`/`style_profile`
are checked via their own tables; the rest via the profiles row. Gaps are
sorted tier-first; a missing profile returns a single `{"field": "profile"}`
gap. The `profile_gaps` tool exposes it; `/setup` step 5 says raise ONE gap
at a time when contextually useful — never a form-wall. LinkedIn guided
import stays on `import_from_url_findings`.

## Design decisions

- **Structurally zero-LLM.** There is no LLM parse path at all: the client LLM
  (already paid by the user) does richer interpretation; the server extracts
  only what regexes prove (AGENTS.md §1.1). Titles/seniority/sectors are
  client proposals, never server inventions (S5.3).
- **None / [], never invent.** Low confidence -> `None` or empty lists + human
  confirmation, not a guess persisted into the profile (§1.4 never-fabricate).
- **Read-only tool.** `parse_cv` cannot write: the only write path is
  `update_profile` after the human confirms, so a pasted CV can never silently
  overwrite a profile.
- **Enums over free text for modality.** Hints reuse profile enums so confirmed
  values drop straight into `update_profile`; B2B/invoice stay narrative
  signals because they are not `EmploymentType` members.
- **Bounded quantifiers everywhere.** All regexes that eat arbitrary pasted
  text carry explicit length caps — see Gotchas.

## Testing

- `tests/test_cv_parser.py` (18 tests): contact extraction (name from
  label/header; None when header starts with email/URL/section; email
  anywhere, phone header-only; date-range rejection; linkedin/github/portfolio
  split), ReDoS linearity probe (200 KB adversarial input < 1 s), tool
  never-writes + oversize rejection, registration pin, plus S5.3 hint cases
  (modality + allowlisted skills; empty when unknown; B2B/invoice → signals
  only; frequency+alpha sort; hard cap 12; hybrid/onsite/full_time/part_time).
- `tests/test_mcp_server.py`: `/setup` prompt is CV-first and names
  `setup_hints`; `SERVER_INSTRUCTIONS` / `parse_cv` breadcrumb mention CV-first.
- `tests/test_profile_gaps.py` (4 tests): required-tier-first ordering, rich
  profile -> `[]`, no profile -> setup gap, tool response shape.

## Gotchas

- **ReDoS was a real P1** (S5 final-review gate, commit `66e717b`): the
  original unbounded `[\w.+-]+@` backtracked quadratically (measured 11 s @
  80 KB). Bounded to `{1,64}@{1,255}.{2,24}` -> linear at any size; the
  `MAX_CV_CHARS` tool cap and the <1 s regression test pin the fix. Any new
  regex here (including skill/modality patterns) must ship with bounded
  quantifiers / `\b` + `re.escape`.
- **Two name anomalies shipped before the gate**: a phone-only header line and
  a bare `Name:` label were returned as the candidate's name. Both are now
  `None` with dedicated tests — extend `_extract_name` guards, never relax
  them toward guessing.
- The phone threshold is deliberately 9 digits, not the donor's 7: 7 let
  8-digit date ranges through as phones.
- `portfolio` was double-stripped pre-gate (P3); stripping happens once inside
  the URL loop (`cv.py:243`) — don't re-strip at return time.
- **Skills allowlist is YAGNI-sized**, not exhaustive. Unknown tech never
  appears in `skills_top`; the client may still propose titles from free
  `cv_text` after human CONFIRM — do not "fix" that by inventing skills
  server-side.
- Card id `S5.3` is shared with CLI packaging (`S5.3_cli_packaging`); this
  module's card slug is `S5.3_cv_setup_hints`.
