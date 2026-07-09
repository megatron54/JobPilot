"""Integration tests for the Autopilot FastAPI app via TestClient."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.automation.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    # Point the service at a temp data dir before the lifespan runs.
    monkeypatch.setenv("AUTOPILOT_DATA_DIR", str(tmp_path))
    from app.automation import config as cfg

    monkeypatch.setattr(cfg.settings, "data_dir", str(tmp_path))
    with TestClient(app) as c:
        yield c


def test_health(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["service"] == "autopilot"


def test_session_lifecycle(client: TestClient) -> None:
    # Initially no session
    resp = client.get("/autopilot/session")
    assert resp.json()["has_session"] is False

    # Set cookies
    resp = client.post(
        "/autopilot/session",
        json={"li_at": "tok123", "jsessionid": '"ajax:42"'},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["has_session"] is True
    assert body["li_at_present"] is True
    assert body["jsessionid_present"] is True


def test_criteria_roundtrip(client: TestClient) -> None:
    criteria = {
        "keywords": ["React", "TypeScript"],
        "location": "Madrid",
        "remote": True,
        "experience_levels": ["3", "4"],
        "job_types": ["F"],
        "posted_within_hours": 24,
        "excluded_companies": [],
        "required_keywords": [],
        "excluded_keywords": [],
    }
    resp = client.put("/autopilot/settings/criteria", json=criteria)
    assert resp.status_code == 200
    assert resp.json()["success"] is True

    resp = client.get("/autopilot/settings/criteria")
    body = resp.json()
    assert body["keywords"] == ["React", "TypeScript"]
    assert body["location"] == "Madrid"
    assert body["remote"] is True


def test_config_roundtrip(client: TestClient) -> None:
    config = {
        "enabled": True,
        "schedule_hour": 8,
        "schedule_minute": 30,
        "schedule_days": [0, 1, 2],
        "max_connections_per_day": 10,
        "max_messages_per_day": 20,
        "max_applies_per_day": 15,
        "score_threshold": 70,
        "top_n_generate": 5,
    }
    resp = client.put("/autopilot/settings/config", json=config)
    assert resp.status_code == 200

    resp = client.get("/autopilot/settings/config")
    body = resp.json()
    assert body["enabled"] is True
    assert body["schedule_hour"] == 8
    assert body["score_threshold"] == 70


def test_queue_empty(client: TestClient) -> None:
    resp = client.get("/autopilot/queue")
    assert resp.status_code == 200
    assert resp.json()["actions"] == []


def test_pipeline_status_idle(client: TestClient) -> None:
    resp = client.get("/autopilot/status")
    assert resp.status_code == 200
    assert resp.json()["status"] == "idle"


def test_jobs_empty(client: TestClient) -> None:
    resp = client.get("/autopilot/jobs")
    assert resp.status_code == 200
    body = resp.json()
    assert body["jobs"] == []
    assert body["total"] == 0


def test_discover_requires_keywords(client: TestClient) -> None:
    from app.automation.session import session as sess

    sess.set_cookies("tok", "ajax:1")
    # No criteria saved yet -> no keywords (guest mode needs no session)
    resp = client.post("/autopilot/discover")
    assert resp.status_code == 400
    assert "keyword" in resp.json()["detail"].lower()
    sess.clear()
