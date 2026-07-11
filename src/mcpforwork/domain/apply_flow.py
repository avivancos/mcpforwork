"""Application state machine + step-plan builder (pure).

THE consent invariant, made structural: `STEP_KINDS` — the full vocabulary this
builder can emit — does not contain "submit". A submit decision exists only in
`services/apply.request_submit`, which at consent level 0 always routes to the
human. The state machine cannot skip `awaiting_human` on the way to `submitted`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

# The ONLY step kinds a plan may contain. Deliberately no "submit".
STEP_KINDS = frozenset({"navigate", "fill", "upload", "answer", "review", "verify"})

STATES = ("draft", "filling", "awaiting_human", "submitted", "verified", "abandoned")

ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "draft": frozenset({"filling", "abandoned"}),
    "filling": frozenset({"awaiting_human", "abandoned"}),
    "awaiting_human": frozenset({"filling", "submitted", "abandoned"}),
    "submitted": frozenset({"verified"}),
    "verified": frozenset(),
    "abandoned": frozenset(),
}


def can_transition(current: str, target: str) -> bool:
    return target in ALLOWED_TRANSITIONS.get(current, frozenset())


def build_steps(
    finding: Mapping[str, Any],
    profile: Mapping[str, Any],
    assets: Sequence[Mapping[str, Any]],
    playbook: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """The ordered step plan the client executes in the USER'S browser.

    Ends at `review` — the human inspects the filled form; submission is only
    reachable through request_submit."""
    steps: list[dict[str, Any]] = [
        {
            "step_id": 1,
            "kind": "navigate",
            "instruction": f"Open the posting's apply page: {finding['url']}",
            "evidence": "none",
        },
        {
            "step_id": 2,
            "kind": "fill",
            "instruction": (
                "Fill the visible form fields from the candidate data (value_refs). "
                "For any question you cannot map, call resolve_field — never invent."
            ),
            "value_refs": {
                "full_name": profile.get("full_name"),
                "contact_email": profile.get("contact_email"),
                "city": profile.get("city"),
                "links": profile.get("links") or {},
            },
            "evidence": "none",
        },
    ]
    step_id = 3
    if assets:
        newest = assets[0]
        steps.append(
            {
                "step_id": step_id,
                "kind": "upload",
                "instruction": (
                    "Upload the CV/cover file where the form asks for it — call "
                    "get_asset_file(asset_id) for a local file path."
                ),
                "asset_ref": {"asset_id": newest.get("id"), "asset_type": newest.get("asset_type")},
                "evidence": "none",
            }
        )
        step_id += 1
    if playbook.get("quirks"):
        steps.append(
            {
                "step_id": step_id,
                "kind": "answer",
                "instruction": f"Portal quirks to expect: {playbook['quirks']}",
                "evidence": "none",
            }
        )
        step_id += 1
    steps.append(
        {
            "step_id": step_id,
            "kind": "review",
            "instruction": (
                "STOP. Show the human the fully filled form (screenshot). Then call "
                "request_submit — the human decides; never click Submit yourself."
            ),
            "evidence": "screenshot",
        }
    )
    return steps
