"""HTTP-level regression tests for the main FastAPI app's security fixes:
CORS, path traversal on CV upload, upload size limit, and SSRF guard on the
job-scraping endpoints."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings


@pytest.fixture
def client(tmp_path: Path, monkeypatch) -> TestClient:
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    monkeypatch.setattr(settings, "cv_dir", str(tmp_path / "cvs"))
    monkeypatch.setattr(settings, "jobs_dir", str(tmp_path / "jobs"))
    monkeypatch.setattr(settings, "outputs_dir", str(tmp_path / "outputs"))

    from app.main import app  # imported lazily so the monkeypatched settings apply

    with TestClient(app) as c:
        yield c


class TestCors:
    def test_wildcard_origin_is_not_reflected(self, client: TestClient):
        resp = client.get("/api/health", headers={"Origin": "https://evil.example.com"})
        assert resp.headers.get("access-control-allow-origin") != "*"
        assert resp.headers.get("access-control-allow-origin") != "https://evil.example.com"

    def test_allowed_origin_is_reflected(self, client: TestClient):
        resp = client.get("/api/health", headers={"Origin": "http://localhost:3000"})
        assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"


class TestUploadCvSecurity:
    def test_upload_rejects_unsupported_extension(self, client: TestClient):
        resp = client.post(
            "/api/cvs/upload",
            files={"file": ("evil.exe", b"MZ...", "application/octet-stream")},
        )
        assert resp.status_code == 400

    def test_upload_sanitizes_traversal_in_filename(self, client: TestClient, tmp_path: Path):
        """A crafted filename with path traversal must be neutralized to a
        plain basename inside cv_dir, never escaping it."""
        resp = client.post(
            "/api/cvs/upload",
            files={"file": ("../../evil.txt", b"hello", "text/plain")},
        )
        assert resp.status_code == 200
        cv_dir = Path(settings.cv_dir)
        # The file must exist inside cv_dir under some sanitized name, and
        # nothing must have been written outside of it.
        assert any(cv_dir.iterdir())
        assert not (tmp_path / "evil.txt").exists()

    def test_upload_enforces_size_limit(self, client: TestClient):
        big_content = b"a" * (21 * 1024 * 1024)  # just over the 20MB limit
        resp = client.post(
            "/api/cvs/upload",
            files={"file": ("big.txt", big_content, "text/plain")},
        )
        assert resp.status_code == 413


class TestScrapeSsrf:
    def test_scrape_rejects_loopback_url(self, client: TestClient):
        resp = client.post("/api/jobs/scrape", json={"url": "http://127.0.0.1:11434/api/tags"})
        assert resp.status_code == 400

    def test_scrape_rejects_file_scheme(self, client: TestClient):
        resp = client.post("/api/jobs/scrape", json={"url": "file:///etc/passwd"})
        assert resp.status_code == 400

    def test_scrape_and_save_rejects_private_ip(self, client: TestClient):
        resp = client.post(
            "/api/jobs/scrape-and-save", json={"url": "http://192.168.1.1/job"}
        )
        assert resp.status_code == 400

    def test_create_job_offer_rejects_unsafe_url(self, client: TestClient):
        resp = client.post("/api/jobs", json={"url": "http://169.254.169.254/latest/meta-data/"})
        assert resp.status_code == 400


class TestJobPathTraversal:
    def test_get_nonexistent_job_returns_404_not_500(self, client: TestClient):
        resp = client.get("/api/jobs/../../etc/passwd")
        assert resp.status_code in (404, 400)

    def test_delete_nonexistent_job_returns_404(self, client: TestClient):
        resp = client.delete("/api/jobs/does-not-exist")
        assert resp.status_code == 404
