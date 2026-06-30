"""Tests for the LLM scorer and pipeline orchestrator (mocked LLM)."""

from __future__ import annotations

import pytest

from app.automation.database import Database
from app.automation.jobs_repository import JobsRepository
from app.automation.linkedin.search import JobStub
from app.automation.models import SearchCriteria
from app.automation.pipeline import orchestrator, scorer
from app.automation.pipeline import llm as llm_mod
from app.automation.pipeline.state import PipelineState
from app.automation.profile import UserProfile
from app.automation.session import LinkedInSession

pytestmark = pytest.mark.asyncio


async def test_score_job_parses_llm_output(monkeypatch) -> None:
    async def fake_json(**kwargs):
        return {
            "score": 87,
            "recommendation": "strong_match",
            "match_reasons": ["React match", "Remote"],
            "deal_breakers": [],
            "missing_skills": ["GraphQL"],
        }

    monkeypatch.setattr(scorer.llm, "generate_json", fake_json)
    result = await scorer.score_job(
        {"job_id": "1", "title": "React Dev"}, UserProfile(key_skills=["React"])
    )
    assert result.score == 87.0
    assert result.recommendation == "strong_match"
    assert "GraphQL" in result.missing_skills


async def test_score_job_handles_llm_error(monkeypatch) -> None:
    async def fail(**kwargs):
        raise llm_mod.LLMError("boom")

    monkeypatch.setattr(scorer.llm, "generate_json", fail)
    result = await scorer.score_job({"job_id": "1"}, UserProfile())
    assert result.score == 0.0
    assert result.recommendation == "skip"


async def test_score_clamps_out_of_range(monkeypatch) -> None:
    async def fake_json(**kwargs):
        return {"score": 150, "recommendation": "strong_match"}

    monkeypatch.setattr(scorer.llm, "generate_json", fake_json)
    result = await scorer.score_job({"job_id": "1"}, UserProfile())
    assert result.score == 100.0


async def test_pipeline_filters_and_scores(db: Database, monkeypatch) -> None:
    # Seed discovered jobs (unscored)
    repo = JobsRepository(db)
    await repo.upsert_stub(JobStub(job_id="good", title="React Developer", company="Acme"))
    await repo.upsert_stub(JobStub(job_id="bad", title="PHP Developer", company="Acme"))
    # Add descriptions
    await db.execute(
        "UPDATE discovered_jobs SET description = ? WHERE job_id = ?",
        ("We use React and TypeScript", "good"),
    )
    await db.execute(
        "UPDATE discovered_jobs SET description = ? WHERE job_id = ?",
        ("Legacy PHP work", "bad"),
    )

    # Mock the LLM scorer
    async def fake_score(job, profile):
        from app.automation.pipeline.scorer import ScoreResult

        return ScoreResult(job_id=job["job_id"], score=85.0, recommendation="good")

    monkeypatch.setattr(orchestrator, "score_job", fake_score)
    monkeypatch.setattr(orchestrator, "load_profile", lambda: UserProfile(key_skills=["React"]))

    session = LinkedInSession()
    session.set_cookies("tok", "ajax:1")
    state = PipelineState()
    criteria = SearchCriteria(keywords=["Developer"], excluded_keywords=["PHP"])

    result = await orchestrator.run_pipeline(
        db, session, criteria, state, do_discovery=False
    )

    # "bad" is filtered out by excluded keyword PHP; "good" gets scored
    assert result.filtered_out == 1
    assert result.scored == 1
    assert state.status == "completed"

    top = await repo.top_scored(limit=10, min_score=60.0)
    assert len(top) == 1
    assert top[0]["job_id"] == "good"


async def test_pipeline_cancellation(db: Database, monkeypatch) -> None:
    repo = JobsRepository(db)
    await repo.upsert_stub(JobStub(job_id="j1", title="Dev", company="X"))

    monkeypatch.setattr(orchestrator, "load_profile", lambda: UserProfile())

    session = LinkedInSession()
    session.set_cookies("tok", "ajax:1")
    state = PipelineState()

    # Request cancellation mid-run (during the pre-filter stage). The post-filter
    # cancellation check should then stop the pipeline before scoring.
    from app.automation.pipeline.prefilter import FilterDecision

    def cancel_during_filter(job, profile, criteria):
        state.request_cancel()
        return FilterDecision(True)

    monkeypatch.setattr(orchestrator, "prefilter_job", cancel_during_filter)

    result = await orchestrator.run_pipeline(
        db, session, SearchCriteria(keywords=["x"]), state, do_discovery=False
    )
    assert state.status == "cancelled"
    assert result.scored == 0
