# CV parsing & progressive onboarding (parse_cv + profile_gaps)

> The zero-LLM onboarding extraction path: `domain/cv.py` parses pasted CV text
> into high-confidence contact fields (never inventing), the `parse_cv` MCP tool
> returns them for human CONFIRMation, and `profile_gaps` drives progressive
> Tier-2 profile completion during /setup. Cards (latest first): S5.2, S5.1.

## How it works

**Parser.** `extract_profile_from_cv(cv_text)` (`src/mcpforwork/domain/cv.py:70`)
is pure stdlib regex, no I/O. Returns `{candidate: {full_name, contact_email,
phone, linkedin, github, portfolio}, cv_text}`; any low-confidence field is
`None` — the client asks the human instead of inventing.

- `_header_block` (`cv.py:34`) bounds name/phone extraction to the leading
  lines before the first section header (max 12 non-blank), so an EXPERIENCE
  title can never be mis-extracted as the candidate's name.
- `_extract_name` (`cv.py:48`): an explicit `Name:` label wins; otherwise the
  first header line that is not an email/URL/section header, not a bare field
  label (trailing `:`), not phone-like (>=7 digits), and not a sentence (>5
  words). Anything ambiguous -> `None`.
- Email is scanned over the whole document (`cv.py:74`) — contact info often
  sits at the bottom. Phone is header-only and needs >=9 digits (`cv.py:76-84`),
  which rejects date ranges like `2020-2023` (8 digits).
- LinkedIn/GitHub are matched by dedicated regexes; `portfolio` is the first
  remaining URL (`cv.py:86-94`). All values are trailing-punctuation stripped.

**Tool.** `parse_cv` (`src/mcpforwork/entrypoints/mcp/server.py:581`) rejects
input over `MAX_CV_CHARS` (200_000, `cv.py:21`), returns the extraction, and
never writes the profile. Its `next_action` (`entrypoints/mcp/guidance.py:45`)
instructs: CONFIRM with the human, then `update_profile` with confirmed values
+ `cv_text`. The /setup prompt step 3 encodes the same flow (`server.py:625`).

**Progressive Tier 2.** `profile_gaps(uow, user_id)`
(`src/mcpforwork/services/profiles.py:201`) walks `_GAP_CATALOGUE`
(`profiles.py:181-198`) — `(field, tier, why)` tuples: tier 1 = required
intake, tier 2 = progressive unlocks (achievements bank first, then style
sample, links, deal_breakers, availability). `achievements`/`style_profile`
are checked via their own tables; the rest via the profiles row. Gaps are
sorted tier-first; a missing profile returns a single `{"field": "profile"}`
gap. The `profile_gaps` tool (`server.py:572`) exposes it; /setup step 4 says
raise ONE gap at a time when contextually useful — never a form-wall
(`server.py:627`). LinkedIn guided import stays on `import_from_url_findings`.

## Design decisions

- **Structurally zero-LLM.** There is no LLM parse path at all: the client LLM
  (already paid by the user) does richer interpretation; the server extracts
  only what regexes prove (AGENTS.md §1.1).
- **None, never invent.** Low confidence -> `None` + human confirmation, not a
  guess persisted into the profile (§1.4 never-fabricate).
- **Read-only tool.** `parse_cv` cannot write: the only write path is
  `update_profile` after the human confirms, so a pasted CV can never silently
  overwrite a profile.
- **Bounded quantifiers everywhere.** All regexes that eat arbitrary pasted
  text carry explicit length caps — see Gotchas.

## Testing

- `tests/test_cv_parser.py` (13 tests): ported donor behaviors (name from
  label/header; None when header starts with email/URL/section; email
  anywhere, phone header-only; date-range rejection; linkedin/github/portfolio
  split), a ReDoS linearity probe (200 KB adversarial input < 1 s), tool
  never-writes + oversize rejection, and a registration pin for both tools.
- `tests/test_profile_gaps.py` (4 tests): required-tier-first ordering, rich
  profile -> `[]`, no profile -> setup gap, tool response shape.

## Gotchas

- **ReDoS was a real P1** (S5 final-review gate, commit `66e717b`): the
  original unbounded `[\w.+-]+@` backtracked quadratically (measured 11 s @
  80 KB). Bounded to `{1,64}@{1,255}.{2,24}` -> linear at any size; the
  `MAX_CV_CHARS` tool cap and the <1 s regression test pin the fix. Any new
  regex here must ship with bounded quantifiers.
- **Two name anomalies shipped before the gate**: a phone-only header line and
  a bare `Name:` label were returned as the candidate's name. Both are now
  `None` with dedicated tests — extend `_extract_name` guards, never relax
  them toward guessing.
- The phone threshold is deliberately 9 digits, not the donor's 7: 7 let
  8-digit date ranges through as phones.
- `portfolio` was double-stripped pre-gate (P3); stripping happens once inside
  the URL loop (`cv.py:90`) — don't re-strip at return time.
