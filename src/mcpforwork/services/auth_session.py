"""Magic-link + session auth core (pure, dependency-light).

The primitives an account layer needs, with NO HTTP and NO email: the FastAPI
`entrypoints/api/` layer and magic-link delivery are deferred (S6.x). Both the
clock (`now`) and the signing `secret` are injected — the module holds no global
state, so expiry, single-use, and tamper are all deterministic under test.

Security shape:
- The raw magic-link token (`secrets.token_urlsafe`) is returned to the caller
  ONCE to deliver; only its sha256 hash is persisted. A leaked database never
  yields a usable token.
- `magic_link_tokens` is looked up by token_hash BEFORE a user is authenticated,
  so it is not RLS-forced (see the migration) — the hash lookup is the guard.
- Sessions are HMAC-signed with itsdangerous (never hand-rolled); the ABSOLUTE
  expiry is embedded at issue time, so the lifetime is fixed by the issuer and
  cannot be silently widened by a lax reader.

`now` must always be a timezone-aware UTC datetime — the epoch math
(`now.timestamp()`) treats a naive datetime as local time, which would corrupt
expiry across machines/timezones.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime
from typing import Any

from itsdangerous import BadData, URLSafeSerializer

from mcpforwork.ports.db import UnitOfWork

# itsdangerous salt: a fixed namespace for session cookies (NOT the secret).
_SESSION_SALT = "mcpforwork.session.v1"
_DEFAULT_MAX_AGE_S = 14 * 24 * 3600  # 14 days


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _epoch(now: datetime) -> int:
    return int(now.timestamp())


def request_magic_link(
    uow: UnitOfWork, email: str, *, now: datetime, ttl_minutes: int = 15
) -> dict[str, Any]:
    """Find-or-create the account for `email` and mint a single-use magic-link
    token. Returns the RAW token (for the caller to deliver) — only its hash is
    stored. Caller commits."""
    email = email.strip().lower()
    # Reject control chars / interior whitespace (a real mailer would otherwise
    # be vulnerable to CR/LF header injection: "a@b.com\r\nBcc: evil@x.com").
    if (
        "@" not in email
        or email.startswith("@")
        or email.endswith("@")
        or any(ord(c) < 32 or c.isspace() for c in email)
    ):
        return {"error": "a valid email is required"}

    row = uow.fetchone("SELECT id FROM users WHERE email = ?", (email,))
    user_id = row["id"] if row else uow.insert("INSERT INTO users (email) VALUES (?)", (email,))

    raw_token = secrets.token_urlsafe(32)
    expires_at = _epoch(now) + ttl_minutes * 60
    uow.insert(
        "INSERT INTO magic_link_tokens (user_id, token_hash, expires_at) VALUES (?, ?, ?)",
        (user_id, _hash_token(raw_token), expires_at),
    )
    # `email` is the normalized, validated address — callers deliver to this.
    return {"raw_token": raw_token, "expires_at": expires_at, "user_id": user_id, "email": email}


def redeem_magic_link(uow: UnitOfWork, raw_token: str, *, now: datetime) -> dict[str, Any]:
    """Redeem a magic-link token exactly once. Returns the user_id, or an error
    for an unknown / already-used / expired token. Caller commits."""
    row = uow.fetchone(
        "SELECT id, user_id, expires_at, used_at FROM magic_link_tokens WHERE token_hash = ?",
        (_hash_token(raw_token),),
    )
    if row is None:
        return {"error": "invalid token"}
    if row["used_at"] is not None:
        return {"error": "token already used"}
    if row["expires_at"] <= _epoch(now):
        return {"error": "token expired"}

    # Atomic single-use: the `used_at IS NULL` guard makes a concurrent second
    # redemption affect zero rows even if both passed the SELECT above.
    cursor = uow.execute(
        "UPDATE magic_link_tokens SET used_at = ? WHERE id = ? AND used_at IS NULL",
        (_epoch(now), row["id"]),
    )
    if cursor.rowcount == 0:
        return {"error": "token already used"}
    return {"user_id": row["user_id"]}


def issue_session(
    user_id: int, *, secret: str, now: datetime, max_age_s: int = _DEFAULT_MAX_AGE_S
) -> str:
    """Sign a session cookie carrying `user_id` and its ABSOLUTE expiry
    (`now + max_age_s`). The lifetime is fixed at issue time — a reader cannot
    widen it — which closes the fail-open gap of a reader-supplied max age."""
    serializer = URLSafeSerializer(secret, salt=_SESSION_SALT)
    return serializer.dumps({"uid": user_id, "exp": _epoch(now) + max_age_s})


def read_session(value: str, *, secret: str, now: datetime) -> int | None:
    """Return the signed-in user_id, or None if the cookie is tampered, signed
    with a different secret, malformed, or at/past its embedded expiry."""
    if not isinstance(value, str) or not value:
        return None
    serializer = URLSafeSerializer(secret, salt=_SESSION_SALT)
    try:
        data = serializer.loads(value)
    except BadData:  # tampered, wrong secret, or malformed
        return None
    if not isinstance(data, dict):
        return None
    uid, exp = data.get("uid"), data.get("exp")
    # `type(...) is int` rejects bool (bool subclasses int) and any non-int.
    if type(uid) is not int or type(exp) is not int:
        return None
    if _epoch(now) >= exp:  # at or past expiry -> rejected (fail-closed)
        return None
    return uid
