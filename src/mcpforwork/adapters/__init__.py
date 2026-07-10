"""Driven adapters — implementations of the ports.

db (SQLite and Postgres dialects + migrations), billing (Stripe), mail,
files. The SQLite/Postgres split IS the open-core split: every feature must
work on the SQLite adapter with no account.
"""
