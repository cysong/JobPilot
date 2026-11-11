"""Online matching pipeline on a real Postgres (LLM mocked): discover -> classify -> enqueue -> judge."""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select, update

from tests.modules.matching.conftest import LOCAL_DB, requires_db

pytestmark = requires_db

if LOCAL_DB:
    from app.core.config import settings
    from app.modules.auth.models import User
    from app.modules.jobs.models import SeekJob
    from app.modules.matching.families.classifier import classify_missing_titles, resolve_pending_jobs
    from app.modules.matching.families.models import JobRoleFamily
    from app.modules.matching.models import JobMatch
    from app.modules.matching.pipeline import discover_new_jobs, enqueue_matches, judge_queued_matches
    from app.modules.resumes.models import Document, Resume

NOW = datetime.now(timezone.utc)

# id -> (title, city, label, days since listed)
JOBS = {
    1: ("Senior Java Developer", "Christchurch", "Christchurch, Canterbury", 1),
    2: ("QA Engineer", "Christchurch", "Christchurch, Canterbury", 2),
    3: ("Backend Engineer", "Auckland", "Auckland CBD, Auckland", 3),  # location rejection
    4: ("Registered Nurse", "Christchurch", "Christchurch, Canterbury", 4),  # filtered
    5: ("DevOps Engineer", None, "New Zealand", 5),  # adjacent to software_dev
    6: ("Full Stack Developer", "Christchurch", "Christchurch, Canterbury", 40),  # too old
}
TITLE_FAMILY = {"java developer": "software_dev", "qa engineer": "qa_test", "backend engineer": "software_dev",
                "registered nurse": "other", "devops engineer": "devops_platform",
                "full stack developer": "software_dev"}


async def _seed(db, *, qa_family: str | None = None):
    db.add(User(id=1, email="u@example.com", hashed_password="x", full_name="U",
                preferences={"job_locations": ["Christchurch"], "work_rights": "work_visa"}))
    for job_id, (title, city, label, days) in JOBS.items():
        db.add(SeekJob(id=job_id, source_id=f"s{job_id}", title=title, listed_at=NOW - timedelta(days=days),
                       content=f"<p>{title} role.</p><ul><li>Must know the stack</li></ul>",
                       location_city=city, location_label=label))
    db.add(SeekJob(id=7, source_id="s7", title="Java Developer", listed_at=NOW, is_expired=True))
    await db.flush()
    for rid, fam, title in (("res_java", "software_dev", "Java Developer"), ("res_qa", qa_family, "SDET")):
        db.add(Document(id=f"doc_{rid}", root_id=f"doc_{rid}", content=f"## Experience\n- {title} work",
                        content_hash=f"h_{rid}", created_by=1))
        await db.flush()
        db.add(Resume(id=rid, user_id=1, document_id=f"doc_{rid}", title=title, is_draft=False,
                      is_deleted=False, role_family=fam,
                      analysis_result={"work_experiences": [{"duration": ["2016-01", "2022-01"]}]}))
    await db.commit()


def _judgment(resume_id: str, tier: str) -> dict:
    return {
        "decision": "rated", "rejection": None,
        "work_rights": {"requirement": "none", "quote": None, "satisfied": None},
        "security_clearance": {"requirement": "none", "quote": None, "satisfied": None},
        "work_location": {"requirement": "none", "country": None, "quote": None, "satisfied": None},
        "languages": {"required_languages": [], "quote": None, "satisfied": None},
        "employment": {"kind": "employment", "quote": None},
        "other_constraints": [],
        "best_resume_id": resume_id, "is_different_track": False, "seniority_mismatch": False,
        "people_management": {"required": False, "job_quote": None, "candidate_has": False, "resume_quote": None},
        "tech_level": "strong", "tech_items": [{"requirement": "Must know the stack", "is_core": True,
                                                "relation": "same",
                                                "evidence": {"job_quote": "Must know the stack",
                                                             "resume_quote": None}}],
        "experience_level": "strong", "relevant_years": 5.0, "required_years": None,
        "experience_evidence": [], "tier": tier, "tier_reason": "Matches the stack.",
    }


def _gateway(calls: list, *, fail_titles: tuple[str, ...] = ()):
    async def call(agent_id, input_data, context=None, model_override=None):
        calls.append(agent_id)
        if agent_id == "title_classifier":
            titles = json.loads(input_data)["titles"]
            return {"items": [{"title_key": t["title_key"], "role_family": TITLE_FAMILY.get(t["title_key"]),
                               "ambiguous": t["title_key"] not in TITLE_FAMILY} for t in titles]}
        assert agent_id == "match_judge"
        title = re.search(r"\[JOB\]\ntitle: (.+)", input_data).group(1)
        if title in fail_titles:
            raise RuntimeError("Error code: 503 upstream unavailable")
        if context is not None:
            context["ai_call_id"] = f"aic_{len(calls)}"
        return _judgment(re.search(r"=== resume_id: (\S+)", input_data).group(1), "A")
    gateway = AsyncMock()
    gateway.call = AsyncMock(side_effect=call)
    return gateway


async def _classify(db, gateway):
    assert await discover_new_jobs(db) == 5  # jobs 1-5: job 6 is too old, job 7 expired
    await classify_missing_titles(db, gateway)
    await resolve_pending_jobs(db, gateway)


async def _matches(session_factory) -> dict[int, JobMatch]:
    async with session_factory() as db:
        return {m.job_id: m for m in (await db.execute(select(JobMatch))).scalars()}


@pytest.mark.asyncio
async def test_discover_and_enqueue(session_factory):
    calls: list = []
    async with session_factory() as db:
        await _seed(db, qa_family="qa_test")
        await _classify(db, _gateway(calls))
        assert await discover_new_jobs(db) == 0  # idempotent
        counts = await enqueue_matches(db)
    assert counts == {"queued": 3, "location_rejected": 1, "non_employment": 0, "filtered": 1}

    rows = await _matches(session_factory)
    assert set(rows) == {1, 2, 3, 5}
    assert rows[1].status == "queued" and rows[1].family_relation == "same"
    # Job families were settled after the resumes were created: new jobs.
    assert rows[1].candidate_resume_ids == ["res_java"] and rows[1].origin == "new_job"
    assert rows[2].candidate_resume_ids == ["res_qa"]
    assert rows[5].family_relation == "adjacent" and set(rows[5].candidate_resume_ids) == {"res_java", "res_qa"}
    assert rows[5].location_check == "unknown"
    assert (rows[3].status, rows[3].reject_code, rows[3].location_check) == ("rejected", "LOCATION", "rejected")
    assert rows[3].ai_call_id is None and rows[3].tier is None

    async with session_factory() as db:
        assert await enqueue_matches(db) == {"queued": 0, "location_rejected": 0, "non_employment": 0, "filtered": 1}


@pytest.mark.asyncio
async def test_blocklisted_company_is_rejected_without_llm(session_factory):
    calls: list = []
    async with session_factory() as db:
        await _seed(db, qa_family="qa_test")
        await db.execute(update(SeekJob).where(SeekJob.id == 2).values(advertiser_name="Alignerr"))
        await db.commit()
        await _classify(db, _gateway(calls))
        counts = await enqueue_matches(db)
    assert counts["non_employment"] == 1 and counts["queued"] == 2
    row = (await _matches(session_factory))[2]
    assert (row.status, row.reject_code, row.ai_call_id) == ("rejected", "NOT_EMPLOYMENT", None)


@pytest.mark.asyncio
async def test_new_jobs_and_backfill_origin(session_factory):
    calls: list = []
    async with session_factory() as db:
        await _seed(db, qa_family=None)  # second resume not bound yet
        await _classify(db, _gateway(calls))
        await enqueue_matches(db)
        rows = await _matches(session_factory)
        assert rows[1].origin == "new_job" and 4 not in rows  # the nurse job is filtered

        # Binding the second resume to "other" later makes job 4 plannable: a backfill.
        await db.execute(update(Resume).where(Resume.id == "res_qa").values(
            role_family="other", updated_at=datetime.now(timezone.utc)))
        await db.commit()
        assert (await enqueue_matches(db))["queued"] == 1
    rows = await _matches(session_factory)
    assert rows[4].status == "queued" and rows[4].origin == "backfill" and rows[4].family_relation == "same"
    assert rows[1].origin == "new_job"  # existing rows are untouched


@pytest.mark.asyncio
async def test_judge_rates_retries_and_skips_expired(session_factory, monkeypatch):
    monkeypatch.setattr(settings, "MATCH_JUDGE_CONCURRENCY", 2)
    calls: list = []
    gateway = _gateway(calls, fail_titles=("QA Engineer",))
    async with session_factory() as db:
        await _seed(db, qa_family="qa_test")
        await _classify(db, gateway)
        await enqueue_matches(db)
        # Job 5 expires while queued.
        await db.execute(update(SeekJob).where(SeekJob.id == 5).values(is_expired=True))
        await db.commit()

    stats = await judge_queued_matches(session_factory, gateway)
    assert stats["claimed"] == 3
    assert stats["rated"] == 1 and stats["failed_retryable"] == 1 and stats["skipped_expired"] == 1
    rows = await _matches(session_factory)
    rated = rows[1]
    assert (rated.status, rated.tier, rated.resume_id, rated.tech_level) == ("rated", "A", "res_java", "strong")
    assert rated.ai_call_id and rated.judged_at and rated.next_attempt_at is None
    assert rated.prompt_version == settings.MATCH_JUDGE_PROMPT_VERSION
    assert rated.resume_content_hash and rated.job_content_hash and rated.judgment["tier"] == "A"
    retry = rows[2]
    assert retry.status == "failed_retryable" and retry.attempts == 1 and "503" in retry.error
    assert timedelta(minutes=4) < retry.next_attempt_at - datetime.now(timezone.utc) <= timedelta(minutes=5)
    assert rows[5].status == "skipped_expired"

    # Not due yet: nothing to claim.
    assert (await judge_queued_matches(session_factory, gateway))["claimed"] == 0

    # Each due retry consumes one backoff step, then the row fails for good.
    for attempt in range(2, len(settings.MATCH_RETRY_BACKOFF_MINUTES) + 2):
        async with session_factory() as db:
            await db.execute(update(JobMatch).where(JobMatch.job_id == 2).values(next_attempt_at=NOW))
            await db.commit()
        await judge_queued_matches(session_factory, gateway)
        row = (await _matches(session_factory))[2]
        assert row.attempts == attempt
    assert row.status == "failed_final" and row.next_attempt_at is None


@pytest.mark.asyncio
async def test_judge_respects_daily_limit_lease_and_batch(session_factory, monkeypatch):
    monkeypatch.setattr(settings, "MATCH_DAILY_LLM_LIMIT_PER_USER", 1)
    calls: list = []
    gateway = _gateway(calls)
    async with session_factory() as db:
        await _seed(db, qa_family="qa_test")
        await _classify(db, gateway)
        await enqueue_matches(db)
        # A row leased by another run is invisible until the lease ends.
        await db.execute(update(JobMatch).where(JobMatch.job_id == 1).values(
            next_attempt_at=NOW + timedelta(minutes=10)))
        await db.commit()

    stats = await judge_queued_matches(session_factory, gateway)
    assert stats["claimed"] == 1 and stats["limited_users"] == [1]
    rows = await _matches(session_factory)
    # Newest due job first: job 1 is leased, so job 2.
    assert rows[2].status == "rated" and rows[1].status == "queued" and rows[5].status == "queued"
    assert (await judge_queued_matches(session_factory, gateway))["claimed"] == 0  # limit used up

    monkeypatch.setattr(settings, "MATCH_DAILY_LLM_LIMIT_PER_USER", 100)
    monkeypatch.setattr(settings, "MATCH_JUDGE_BATCH_SIZE", 1)
    assert (await judge_queued_matches(session_factory, gateway))["claimed"] == 1  # batch size caps a run
    assert (await _matches(session_factory))[5].status == "rated"
    assert sum(1 for c in calls if c == "match_judge") == 2


@pytest.mark.asyncio
async def test_unbound_resume_is_dropped_from_candidates(session_factory):
    calls: list = []
    gateway = _gateway(calls)
    async with session_factory() as db:
        await _seed(db, qa_family="qa_test")
        await _classify(db, gateway)
        await enqueue_matches(db)
        # The QA resume is deleted while job 2 is queued: no candidate left.
        await db.execute(update(Resume).where(Resume.id == "res_qa").values(is_deleted=True))
        await db.commit()
    await judge_queued_matches(session_factory, gateway)
    rows = await _matches(session_factory)
    assert rows[2].status == "failed_final" and "no candidate" in rows[2].error
    # Job 5 (adjacent, both resumes) is still judged with the remaining resume.
    assert rows[5].status == "rated" and rows[5].resume_id == "res_java"
