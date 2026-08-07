"""Security helpers: safe filenames/slugs, path containment checks, and SSRF-safe URL validation."""

import ipaddress
import re
import socket
from pathlib import Path
from urllib.parse import urlparse

_SAFE_SLUG_RE = re.compile(r"[^a-zA-Z0-9_-]+")


def safe_slug(value: str, default: str = "unknown", max_length: int = 80) -> str:
    """Convert arbitrary user input into a filesystem-safe slug.

    Strips path separators, dots and any other characters that could be used
    for path traversal (`../`, absolute paths, drive letters, etc.).
    """
    value = (value or "").strip().lower().replace(" ", "_")
    value = _SAFE_SLUG_RE.sub("", value)
    value = value.strip("_-.")
    if not value:
        return default
    return value[:max_length]


def safe_join(base_dir: Path, filename: str) -> Path:
    """Join `filename` under `base_dir`, raising ValueError if it would escape it.

    Use this for any filename that originates from user/network input before
    reading, writing or deleting a file.
    """
    base_resolved = base_dir.resolve()
    # Only the final path component is trusted; strip any directory parts.
    name = Path(filename).name
    if not name or name in (".", ".."):
        raise ValueError(f"Invalid filename: {filename!r}")

    candidate = (base_resolved / name).resolve()
    try:
        candidate.relative_to(base_resolved)
    except ValueError:
        raise ValueError(f"Path traversal attempt detected: {filename!r}") from None

    return candidate


_PRIVATE_NETS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),  # link-local, incl. cloud metadata
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


class UnsafeURLError(ValueError):
    """Raised when a URL is not safe to fetch (SSRF protection)."""


def assert_safe_http_url(url: str) -> None:
    """Validate that `url` is a plain http(s) URL that does not resolve to a
    private/loopback/link-local address. Raises UnsafeURLError otherwise.

    This is a best-effort SSRF mitigation: it checks scheme and DNS
    resolution at validation time (TOCTOU against DNS rebinding is out of
    scope for a local personal-use tool, but this blocks the common cases:
    localhost, private ranges, and cloud metadata endpoints).
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise UnsafeURLError(f"Unsupported URL scheme: {parsed.scheme!r}")
    if not parsed.hostname:
        raise UnsafeURLError("URL has no hostname")

    hostname = parsed.hostname
    try:
        addr_infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise UnsafeURLError(f"Could not resolve hostname: {hostname!r}") from exc

    for info in addr_infos:
        ip_str = info[4][0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue
        if any(ip in net for net in _PRIVATE_NETS) or ip.is_reserved or ip.is_multicast:
            raise UnsafeURLError(
                f"URL resolves to a disallowed address ({hostname} -> {ip_str})"
            )
