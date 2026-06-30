"""Send LinkedIn connection requests and messages via the Voyager API.

Both operations are write actions and strictly rate-limited. They are only ever
executed for actions the user has explicitly approved in the queue. See
docs/AUTOPILOT_PLAN.md sections 7 and 10.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from ..linkedin.client import LinkedInClient, LinkedInError
from ..session import LinkedInSession

logger = logging.getLogger("jobpilot.autopilot.connector")

_INVITE_PATH = "/growth/normInvitations"
_MESSAGE_PATH = "/messaging/conversations?action=create"

MAX_NOTE_CHARS = 300


@dataclass
class ConnectOutcome:
    status: str            # sent / failed / invalid
    detail: str = ""


def _profile_id_from_url(profile_url: str) -> str:
    """Extract the public identifier from a /in/{id}/ URL."""
    if not profile_url:
        return ""
    parts = [p for p in profile_url.rstrip("/").split("/") if p]
    if "in" in parts:
        idx = parts.index("in")
        if idx + 1 < len(parts):
            return parts[idx + 1]
    return parts[-1] if parts else ""


async def send_connection_request(
    session: LinkedInSession,
    profile_urn: str,
    note: str = "",
) -> ConnectOutcome:
    """Send a connection invitation with an optional note (<=300 chars).

    `profile_urn` is the member URN/id (e.g. 'ACoAAB...'). The note is truncated
    to LinkedIn's limit.
    """
    if not profile_urn:
        return ConnectOutcome("invalid", "Missing profile id")
    note = (note or "").strip()[:MAX_NOTE_CHARS]

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
