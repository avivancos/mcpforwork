"""The mailer port — how the API delivers a magic-link URL to a user.

A driven seam so delivery (console for self-host, SMTP/provider for hosted) is
swappable without the API knowing which. The raw token lives inside `link`; an
implementation MUST treat the link as a bearer secret (no shared logs, no
third-party analytics).
"""

from __future__ import annotations

from typing import Protocol


class Mailer(Protocol):
    def send_magic_link(self, email: str, link: str) -> None:
        """Deliver the sign-in `link` (which carries the single-use token) to
        `email`. Raising propagates as a 5xx — delivery failure is not silent."""
