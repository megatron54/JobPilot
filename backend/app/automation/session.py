"""LinkedIn session state for the Autopilot service.

Holds the auth cookies (li_at + JSESSIONID) passed from the Tauri host and
derives the csrf-token used by the Voyager API. This is an in-memory singleton;
cookies are never persisted to disk by the Python service (the Tauri host owns
extraction from the browser).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger("jobpilot.autopilot.session")


@dataclass
class LinkedInSession:
    """In-memory LinkedIn auth state."""

    li_at: str = field(default="", repr=False)
    jsessionid: str = field(default="", repr=False)
    _valid: bool | None = field(default=None)

    def set_cookies(self, li_at: str, jsessionid: str = "") -> None:
        self.li_at = li_at.strip()
        # JSESSIONID often comes wrapped in quotes; strip them for the csrf token.
        self.jsessionid = jsessionid.strip().strip('"')
        self._valid = None
        logger.info(
            "LinkedIn session set (li_at=%s chars, jsessionid=%s)",
            len(self.li_at),
            "present" if self.jsessionid else "missing",
        )

    @property
    def has_session(self) -> bool:
        return bool(self.li_at)

    @property
    def csrf_token(self) -> str:
        """The csrf-token header equals the JSESSIONID cookie value."""
        return self.jsessionid

    @property
    def cookie_header(self) -> str:
        parts = []
        if self.li_at:
            parts.append(f"li_at={self.li_at}")
        if self.jsessionid:
            parts.append(f'JSESSIONID="{self.jsessionid}"')
        return "; ".join(parts)

    def mark_valid(self, valid: bool) -> None:
        self._valid = valid

    @property
    def valid(self) -> bool | None:
        return self._valid

    def clear(self) -> None:
        self.li_at = ""
        self.jsessionid = ""
        self._valid = None


# Module-level singleton
session = LinkedInSession()
