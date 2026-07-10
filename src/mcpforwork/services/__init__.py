"""Use cases (application layer).

Signatures take (uow, user_id, ...) explicitly; the caller commits. The
consent, caps, and dedup gates live here so no entrypoint can bypass them.
May not import adapters or entrypoints (enforced by import-linter).
"""
