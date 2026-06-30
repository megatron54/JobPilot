"""Send LinkedIn connection requests and messages via the Voyager API.

Both operations are write actions and strictly rate-limited. They are only ever
executed for actions the user has explicitly approved in the queue. See
docs/AUTOPILOT_PLAN.md sections 7 and 10.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from urllib.parse import urlparse

from ..linkedin.client import LinkedInClient, LinkedInError
from ..session import LinkedInSession

logger = logging.getLogger("jobpilot.autopilot.connector")

_INVITE_PATH = "/growth/normInvitations"
_MESSAGE_PATH = "/messaging/conversations?action=create"

MAX_NOTE_CHARS = 300

# Valid LinkedIn public identifier / member URN shape.
_VALID_ID = re.compile(r"^[A-Za-z0-9_\-]{2,120}$")


@dataclass
class ConnectOutcome:
    status: str            # sent / failed / invalid
    detail: str = ""


def _profile_id_from_url(profile_url: str) -> str:
    """Extract the public identifier from a '/in/{id}/' URL, robustly.

    Parses only the path component (ignoring query/fragment) and validates the
    extracted id to avoid targeting the wrong person.
    """
    if not profile_url:
        return ""
    # Allow passing a bare id/URN directly.
    if "/" not in profile_url and _VALID_ID.match(profile_url):
        return profile_url

    path = urlparse(profile_url).path
    parts = [p for p in path.split("/") if p]
    candidate = ""
    if "in" in parts:
        idx = parts.index("in")
        if idx + 1 < len(parts):
            candidate = parts[idx + 1]
    if not candidate:
        return ""
    return candidate if _VALID_ID.match(candidate) else ""


_URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")


def _sanitize_note(note: str) -> str:
    """Strip URLs and emails - LinkedIn flags connection notes that contain them."""
    cleaned = _URL_RE.sub("", note or "")
    cleaned = _EMAIL_RE.sub("", cleaned)
    return " ".join(cleaned.split()).strip()


async def send_connection_request(
    session: LinkedInSession,
    profile_urn: str,
    note: str = "",
) -> ConnectOutcome:
    """Send a connection invitation with an optional note (<=300 chars).

    `profile_urn` is the member URN/id (e.g. 'ACoAAB...'). The note is sanitized
    (no URLs/emails) and truncated to LinkedIn's limit.
    """
    if not profile_urn:
        return ConnectOutcome("invalid", "Missing profile id")
    note = _sanitize_note(note)[:MAX_NOTE_CHARS]

    body = {
        "invitee": {
            "com.linkedin.voyager.growth.invitation.InviteeProfile": {
                "profileId": profile_urn
            }
        }
    }
    if note:
        body["message"] = note

    try:
        async with LinkedInClient(session) as client:
            await client.post(_INVITE_PATH, body)
        return ConnectOutcome("sent", "Invitation sent")
    except LinkedInError as exc:
        logger.warning("Connection request failed: %s", exc)
        return ConnectOutcome("failed", str(exc))


async def send_message(
    session: LinkedInSession,
    recipient_urn: str,
    text: str,
) -> ConnectOutcome:
    """Send a direct message to a 1st-degree connection."""
    if not recipient_urn:
        return ConnectOutcome("invalid", "Missing recipient")
    text = (text or "").strip()
    if not text:
        return ConnectOutcome("invalid", "Empty message")

    body = {
        "keyVersion": "LEGACY_INBOX",
        "conversationCreate": {
            "eventCreate": {
                "value": {
                    "com.linkedin.voyager.messaging.create.MessageCreate": {
                        "attributedBody": {"text": text, "attributes": []},
                        "attachments": [],
                    }
                }
            },
            "subtype": "MEMBER_TO_MEMBER",
            "recipients": [recipient_urn],
        },
    }
    try:
        async with LinkedInClient(session) as client:
            await client.post(_MESSAGE_PATH, body)
        return ConnectOutcome("sent", "Message sent")
    except LinkedInError as exc:
        logger.warning("Message send failed: %s", exc)
        return ConnectOutcome("failed", str(exc))
