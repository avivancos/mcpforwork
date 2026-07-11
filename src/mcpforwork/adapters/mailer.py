"""Console mailer — the self-host default delivery for magic-link URLs.

Self-host is single-user on the user's own machine, so printing the sign-in link
to stderr IS the delivery channel (the user clicks it), not a leak. Hosted
deployments swap in a real email adapter behind the same `Mailer` port; that
adapter must never log the link.
"""

from __future__ import annotations

import sys


class ConsoleMailer:
    """Prints the magic-link URL to stderr for the local user to open."""

    def send_magic_link(self, email: str, link: str) -> None:
        print(f"[mcpforwork] sign-in link for {email}: {link}", file=sys.stderr)
