"""Helpers for the LinkedIn Voyager "normalized" JSON response format.

Voyager responses contain a `data` block (the result, often referencing
entities by URN) and an `included` array of denormalized entities. These
helpers build a URN index and resolve references defensively, since field
shapes vary across endpoints and API versions.
"""

from __future__ import annotations

from typing import Any


def build_index(payload: dict) -> dict[str, dict]:
    """Map entityUrn -> entity object from the `included` array."""
    index: dict[str, dict] = {}
    for item in payload.get("included", []) or []:
        if isinstance(item, dict):
            urn = item.get("entityUrn")
            if isinstance(urn, str):
                index[urn] = item
    return index


def included_of_type(payload: dict, type_suffix: str) -> list[dict]:
    """Return all included entities whose $type ends with `type_suffix`."""
    out: list[dict] = []
    for item in payload.get("included", []) or []:
        if isinstance(item, dict):
            t = item.get("$type", "")
            if isinstance(t, str) and t.endswith(type_suffix):
                out.append(item)
    return out


def job_id_from_urn(urn: str) -> str:
    """Extract the numeric job id from a jobPosting URN.

    e.g. 'urn:li:fs_jobPosting:1234567890' -> '1234567890'
    """
    if not urn:
        return ""
    return urn.rsplit(":", 1)[-1]


def first(*values: Any, default: str = "") -> str:
    """Return the first non-empty string-able value."""
    for v in values:
        if v:
            return str(v)
    return default


def text_of(value: Any) -> str:
    """Extract text from a Voyager attributed-text object or plain value."""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        if "text" in value and isinstance(value["text"], str):
            return value["text"]
    return ""
