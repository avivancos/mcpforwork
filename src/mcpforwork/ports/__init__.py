"""Port seams — typing.Protocol definitions only.

The named ports: Database/UoW, Mailer, Billing, FileStore, Clock. No
implementations here (those are adapters), and no imports from services,
adapters, or entrypoints (enforced by import-linter).
"""
