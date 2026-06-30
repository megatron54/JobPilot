"""Tests for the LinkedIn session state."""

from __future__ import annotations

from app.automation.session import LinkedInSession


def test_set_cookies_strips_quotes() -> None:
    s = LinkedInSession()
    s.set_cookies("abc123", '"ajax:9876"')
    assert s.li_at == "abc123"
    assert s.jsessionid == "ajax:9876"
    assert s.csrf_token == "ajax:9876"


def test_has_session() -> None:
    s = LinkedInSession()
    assert s.has_session is False
    s.set_cookies("token")
    assert s.has_session is True


def test_cookie_header() -> None:
    s = LinkedInSession()
    s.set_cookies("tok", "ajax:1")
    header = s.cookie_header
    assert "li_at=tok" in header
    assert 'JSESSIONID="ajax:1"' in header


def test_clear() -> None:
    s = LinkedInSession()
    s.set_cookies("tok", "ajax:1")
    s.clear()
    assert s.has_session is False
    assert s.csrf_token == ""


def test_validity_tracking() -> None:
    s = LinkedInSession()
    assert s.valid is None
    s.mark_valid(True)
    assert s.valid is True
