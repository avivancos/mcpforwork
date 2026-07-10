"""Pure domain logic — no I/O, no imports from any other layer.

Home of canonical URL + dedup hashing, scoring, the pack schema, the apply
state machine, generation briefs, and the facts inventory. Enforced by
import-linter: this package may not import services, ports, adapters,
entrypoints, or packs.
"""
