"""Regression tests for app/core/security.py.

These guard against path traversal and SSRF regressions in the shared
security helpers used across the CV/job/scraper endpoints.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.security import (
    UnsafeURLError,
    assert_safe_http_url,
    safe_join,
    safe_slug,
)


class TestSafeSlug:
    def test_strips_path_traversal_sequences(self):
        assert safe_slug("../../etc/passwd") == "etcpasswd"

    def test_lowercases_and_replaces_spaces(self):
        assert safe_slug("My Company Inc.") == "my_company_inc"

    def test_empty_input_returns_default(self):
        assert safe_slug("") == "unknown"
        assert safe_slug("   ") == "unknown"
        assert safe_slug("../../..") == "unknown"

    def test_truncates_to_max_length(self):
        assert len(safe_slug("a" * 500)) == 80


class TestSafeJoin:
    def test_rejects_parent_traversal_by_only_using_basename(self, tmp_path: Path):
        base = tmp_path / "cvs"
        base.mkdir()
        result = safe_join(base, "../../etc/passwd")
        assert result.parent == base
        assert result.name == "passwd"

    def test_rejects_dotdot_only(self, tmp_path: Path):
        base = tmp_path / "cvs"
        base.mkdir()
        with pytest.raises(ValueError):
            safe_join(base, "..")

    def test_rejects_empty_filename(self, tmp_path: Path):
        base = tmp_path / "cvs"
        base.mkdir()
        with pytest.raises(ValueError):
            safe_join(base, "")

    def test_windows_style_traversal_is_neutralized(self, tmp_path: Path):
        base = tmp_path / "cvs"
        base.mkdir()
        result = safe_join(base, "..\\..\\Windows\\System32\\evil.txt")
        # On Windows, backslash is a separator: Path().name strips it down to
        # the final component, so the result must stay under `base`.
        assert result.parent == base

    def test_absolute_path_is_neutralized(self, tmp_path: Path):
        base = tmp_path / "cvs"
        base.mkdir()
        result = safe_join(base, "C:\\Users\\victim\\secret.txt")
        assert result.parent == base
        assert result.name == "secret.txt"

    def test_normal_filename_joins_as_expected(self, tmp_path: Path):
        base = tmp_path / "cvs"
        base.mkdir()
        result = safe_join(base, "resume.pdf")
        assert result == base / "resume.pdf"


class TestAssertSafeHttpUrl:
    def test_rejects_non_http_schemes(self):
        for scheme in ("file:///etc/passwd", "ftp://example.com", "javascript:alert(1)"):
            with pytest.raises(UnsafeURLError):
                assert_safe_http_url(scheme)

    def test_rejects_loopback(self):
        with pytest.raises(UnsafeURLError):
            assert_safe_http_url("http://127.0.0.1:11434/api/tags")
        with pytest.raises(UnsafeURLError):
            assert_safe_http_url("http://localhost:8765/autopilot/status")

    def test_rejects_private_ranges(self):
        for host in ("http://10.0.0.5/", "http://172.16.0.1/", "http://192.168.1.1/"):
            with pytest.raises(UnsafeURLError):
                assert_safe_http_url(host)

    def test_rejects_link_local_and_cloud_metadata(self):
        with pytest.raises(UnsafeURLError):
            assert_safe_http_url("http://169.254.169.254/latest/meta-data/")

    def test_allows_public_https_url(self):
        # www.linkedin.com should resolve to public IPs; this test only
        # exercises the scheme/host validation branch, DNS resolution may
        # legitimately fail in a sandboxed CI runner without network access,
        # in which case UnsafeURLError is still raised but for a different
        # reason (resolution failure) - both are acceptable "did not crash"
        # outcomes here, we only assert it doesn't raise for private IPs.
        try:
            assert_safe_http_url("https://www.linkedin.com/jobs/view/123")
        except UnsafeURLError as exc:
            assert "resolve" in str(exc).lower()

    def test_rejects_url_without_hostname(self):
        with pytest.raises(UnsafeURLError):
            assert_safe_http_url("http://")
