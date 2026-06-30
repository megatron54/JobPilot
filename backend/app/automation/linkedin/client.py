"""LinkedIn Voyager API HTTP client (httpx, async).

Wraps the authenticated Voyager API used by the LinkedIn web frontend. The
client never logs cookie values and raises typed errors for the conditions
that matter most: expired session (401/403), rate limiting (429) and security
challenges (CAPTCHA).

See docs/AUTOPILOT_PLAN.md section 7 for the endpoint and header reference.
"""

from __future__ import annotations

import logging

import httpx

from ..session import LinkedInSession
from .rate_limiter import RateLimiter

logger = logging.getLogger("jobpilot.autopilot.linkedin.client")

VOYAGER_BASE = "https://www.linkedin.com/voyager/api"

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


class LinkedInError(Exception):
    """Base error for LinkedIn client failures."""


class SessionExpiredError(LinkedInError):
    """The li_at cookie is no longer valid (401/403)."""


class RateLimitedError(LinkedInError):
    """LinkedIn returned 429; back off."""


class ChallengeError(LinkedInError):
    """LinkedIn issued a security challenge (CAPTCHA). Stop automation."""


class LinkedInClient:
    """Authenticated async client for the Voyager API."""

    def __init__(
        self,
        session: LinkedInSession,
        rate_limiter: RateLimiter | None = None,
        timeout_s: float = 15.0,
    ) -> None:
        self._session = session
        self._rl = rate_limiter or RateLimiter()
        self._timeout = timeout_s
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "LinkedInClient":
        self._client = httpx.AsyncClient(
            timeout=self._timeout,
            follow_redirects=False,
            headers={"User-Agent": _USER_AGENT},
        )
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _headers(self) -> dict[str, str]:
        if not self._session.has_session:
            raise SessionExpiredError("No LinkedIn session configured")
        return {
            "csrf-token": self._session.csrf_token,
            "cookie": self._session.cookie_header,
            "x-restli-protocol-version": "2.0.0",
            "x-li-lang": "es_ES",
            "x-li-track": (
                '{"clientVersion":"1.13.0","mpVersion":"1.13.0","osName":"web",'
                '"timezoneOffset":1,"timezone":"Europe/Madrid",'
                '"deviceFormFactor":"DESKTOP","mpName":"voyager-web",'
                '"displayDensity":1,"displayWidth":1920,"displayHeight":1080}'
            ),
            "accept": "application/vnd.linkedin.normalized+json+2.1",
            "x-li-page-instance": "urn:li:page:d_flagship3_search_srp_jobs;jobpilot",
            "sec-fetch-site": "same-origin",
            "sec-fetch-mode": "cors",
            "referer": "https://www.linkedin.com/jobs/",
        }

    async def get(self, path: str, params: dict | None = None) -> dict:
        """GET a Voyager endpoint. `path` is relative to the Voyager base."""
        if self._client is None:
            raise RuntimeError("Client not opened; use 'async with'")

        url = f"{VOYAGER_BASE}{path}"
        async with self._rl:
            try:
                resp = await self._client.get(url, params=params, headers=self._headers())
            except httpx.HTTPError as exc:
                raise LinkedInError(f"HTTP error: {exc}") from exc

        self._raise_for_status(resp)
        try:
            return resp.json()
        except ValueError as exc:
            raise LinkedInError(f"Invalid JSON response: {exc}") from exc

    async def post(self, path: str, json_body: dict) -> dict:
        if self._client is None:
            raise RuntimeError("Client not opened; use 'async with'")

        url = f"{VOYAGER_BASE}{path}"
        async with self._rl:
            try:
                resp = await self._client.post(url, json=json_body, headers=self._headers())
            except httpx.HTTPError as exc:
                raise LinkedInError(f"HTTP error: {exc}") from exc

        self._raise_for_status(resp)
        if not resp.content:
            return {}
        try:
            return resp.json()
        except ValueError:
            return {}

    @staticmethod
    def _raise_for_status(resp: httpx.Response) -> None:
        status = resp.status_code
        if status in (401, 403):
            raise SessionExpiredError(
                "LinkedIn session expired. Re-login in your browser."
            )
        if status == 429:
            raise RateLimitedError("Rate limited by LinkedIn (429). Backing off.")
        if status == 999:
            raise RateLimitedError("LinkedIn blocked the request (999).")
        # A challenge often manifests as a redirect to /checkpoint.
        location = resp.headers.get("location", "")
        if "checkpoint" in location or "challenge" in location:
            raise ChallengeError("LinkedIn issued a security challenge (CAPTCHA).")
        if status >= 400:
            raise LinkedInError(f"LinkedIn returned status {status}")

    async def validate_session(self) -> bool:
        """Lightweight check that the current session works."""
        try:
            await self.get("/me")
            self._session.mark_valid(True)
            return True
        except SessionExpiredError:
            self._session.mark_valid(False)
            return False
        except LinkedInError:
            # Network or other transient error - don't mark invalid.
            return False
