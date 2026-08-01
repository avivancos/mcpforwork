# S<sprint>.<n> — <short imperative title>

**Epic:** <epic / area>
**Estimated effort:** <~X h>

## Goal

<What and why, 2–4 lines. Describe the outcome, not the implementation.>

## Spec

<The contract that makes this task verifiable: endpoints, request/response
schemas, validations, edge cases, exact expected behavior. Include examples.>

## Files to create/modify

- `path/to/file` — note (mark NEW if created)

## Dependencies added

<!-- one justification line per new dependency, or "None" -->

## Definition of Done

- [ ] <verifiable acceptance criterion>
- [ ] <verifiable acceptance criterion>
- [ ] Targeted tests green via `uv run pytest <paths>`
- [ ] Fused review gate: test-code-reviewer PASS (incl. regression audit)
- [ ] Post-task audit done (visual for UI / smoke for tool/API/CLI)

## Improvements noted
<!-- Fill during execution. Raise a follow-up task per item. -->

## Pending human testing
<!-- ONLY if this card moves to need_human_testing/. Provide:
     1) what was built + why the agent can't close verification
     2) exact reproducible steps for the human (paths, commands, data, account)
     3) expected result + pass/fail criteria
     4) risks to watch (money, real data, irreversible actions)
     5) what the agent already verified -->
