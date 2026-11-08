"""Database integration tests for matching v3 (real Postgres, LLM mocked).

Skipped unless MATCHING_TEST_DATABASE_URL points at a throwaway local database,
e.g. postgresql+asyncpg://postgres:pg@localhost:55432/migtest. The schema is
recreated from ORM metadata for every test module run.
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from tests.modules.matching.conftest import LOCAL_DB, requires_db

pytestmark = requires_db

if LOCAL_DB:
    from app.modules.auth.models import User
    from app.modules.jobs.models import SeekJob
    from app.modules.matching.families.classifier import (
        TitleToClassify,
        classify_missing_titles,
        classify_titles,
        register_jobs,
        resolve_pending_jobs,
    )
    from app.modules.matching.families.models import JobRoleFamily, JobTitleFamily
    from app.modules.matching.judge.service import load_job_context, load_user_context
    from app.modules.matching.models import JobMatch
    from app.modules.resumes.models import Document, Resume, ResumeSkill
    from app.modules.users.models import UserSkill
    from app.shared.enums import ProficiencyLevel

NOW = datetime.now(timezone.utc)


async def _seed(db):
    user = User(id=1, email="u@example.com", hashed_password="x", full_name="U",
                preferences={"job_locations": ["Christchurch"], "work_rights": "work_visa"})
    db.add(user)
    jobs = [
        SeekJob(id=101, source_id="s101", title="Senior Software Engineer", listed_at=NOW,
                content="<ul><li>5+ years Java</li></ul>", location_city="Canterbury",
                location_label="Addington, Canterbury"),
        SeekJob(id=102, source_id="s102", title="Software Engineer (Contract)", listed_at=NOW),
        SeekJob(id=103, source_id="s103", title="Automation Engineer", listed_at=NOW,
                content="<p>Write Playwright tests for our web app.</p>"),
    ]
    db.add_all(jobs)
    await db.flush()
    doc = Document(id="doc1", root_id="doc1", content="## Experience\n- Built Java services",
                   content_hash="h", created_by=1)
    db.add(doc)
    await db.flush()
    db.add(Resume(id="res1", user_id=1, document_id="doc1", title="Java Developer", is_draft=False,
                  is_deleted=False, role_family="software_dev",
                  analysis_result={"work_experiences": [{"duration": ["2016-01", "2022-01"]}]}))
    await db.flush()
    db.add(UserSkill(id="us1", user_id=1, skill_name="Azure", proficiency_level=ProficiencyLevel.INTERMEDIATE))
    db.add(ResumeSkill(id="rs1", user_id=1, resume_id="res1", skill_name="Azure",
                       proficiency_level=ProficiencyLevel.INTERMEDIATE,
                       extracted_from=[{"category": "project", "quotes": ["Deployed to Azure"]}]))
    await db.commit()


def _title_gateway(mapping):
    async def call(agent_id, input_data, context=None, model_override=None):
        import json
        if agent_id == "title_classifier":
            titles = json.loads(input_data)["titles"]
            return {"items": [
                {"title_key": t["title_key"], "role_family": mapping.get(t["title_key"]),
                 "ambiguous": mapping.get(t["title_key"]) is None}
                for t in titles
            ]}
        assert agent_id == "job_family_reader"
        if context is not None:
            context["ai_call_id"] = "aic_jd"
        return {"role_family": "qa_test", "reason": "Playwright tests"}
    gateway = AsyncMock()
    gateway.call = AsyncMock(side_effect=call)
    return gateway


@pytest.mark.asyncio
async def test_family_pipeline_title_cache_and_jd_read(session):
    await _seed(session)
    jobs = (await session.execute(select(SeekJob.id, SeekJob.title))).all()
    assert await register_jobs(session, [(j.id, j.title) for j in jobs]) == 3
    assert await register_jobs(session, [(101, "Senior Software Engineer")]) == 0  # idempotent
    await session.commit()

    gateway = _title_gateway({"software engineer": "software_dev"})
    written = await classify_missing_titles(session, gateway)
    assert written == 2  # "software engineer" (shared by 101 and 102) + "automation engineer"

    counts = await resolve_pending_jobs(session, gateway)
    assert counts == {"title_cache": 2, "jd_read": 1, "failed": 0}

    rows = {r.job_id: r for r in (await session.execute(select(JobRoleFamily))).scalars()}
    assert rows[101].role_family == rows[102].role_family == "software_dev"
    assert rows[101].method == "title_cache"
    assert rows[103].role_family == "qa_test"
    assert rows[103].method == "jd_read"
    assert rows[103].ai_call_id == "aic_jd"
    assert all(r.families_version == "f1" for r in rows.values())


@pytest.mark.asyncio
async def test_admin_title_rows_are_not_overwritten(session):
    await _seed(session)
    session.add(JobTitleFamily(id="jtf_admin", title_key="software engineer", example_title="SE",
                               status="classified", role_family="qa_test", source="admin",
                               families_version="f1", classifier_version="manual"))
    await session.commit()

    gateway = _title_gateway({"software engineer": "software_dev", "data engineer": "data_engineering"})
    await classify_titles(session, gateway, [TitleToClassify("software engineer", "SE"),
                                             TitleToClassify("data engineer", "DE")])
    rows = {r.title_key: r for r in (await session.execute(select(JobTitleFamily))).scalars()}
    assert rows["software engineer"].role_family == "qa_test"  # admin row kept
    assert rows["data engineer"].role_family == "data_engineering"


@pytest.mark.asyncio
async def test_failed_batch_does_not_stop_others(session):
    await _seed(session)
    calls = {"n": 0}

    async def call(agent_id, input_data, context=None, model_override=None):
        calls["n"] += 1
        if calls["n"] == 1:
            raise TimeoutError("boom")
        return {"items": [{"title_key": "b", "role_family": "other", "ambiguous": False}]}

    gateway = AsyncMock()
    gateway.call = AsyncMock(side_effect=call)
    written = await classify_titles(session, gateway, [TitleToClassify("a", "A"), TitleToClassify("b", "B")],
                                    batch_size=1)
    assert written == 1


@pytest.mark.asyncio
async def test_jd_read_failures_mark_job_failed_after_max_attempts(session):
    await _seed(session)
    await register_jobs(session, [(103, "Automation Engineer")])
    session.add(JobTitleFamily(id="jtf_amb", title_key="automation engineer", example_title="AE",
                               status="ambiguous", source="llm", families_version="f1", classifier_version="c"))
    await session.commit()
    gateway = AsyncMock()
    gateway.call = AsyncMock(side_effect=RuntimeError("provider down"))

    for _ in range(3):
        await resolve_pending_jobs(session, gateway)
    row = await session.get(JobRoleFamily, 103)
    assert row.status == "failed"
    assert row.attempts == 3
    assert "provider down" in row.error


@pytest.mark.asyncio
async def test_load_user_and_job_context(session):
    await _seed(session)
    user = await load_user_context(session, 1)
    assert user.job_locations == ("Christchurch",)
    assert user.conditions.work_rights == "work_visa"
    assert user.conditions.security_clearance is None
    assert [r.id for r in user.resumes] == ["res1"]
    assert user.resumes[0].work_experiences[0]["duration"] == ["2016-01", "2022-01"]
    assert user.skills[0].skill_name == "Azure"
    assert user.skills[0].proficiency == ProficiencyLevel.INTERMEDIATE.value
    assert user.skills[0].evidence == ("Deployed to Azure",)

    job = await load_job_context(session, 101)
    assert job.job.description == "- 5+ years Java"
    assert job.location_city == "Canterbury"


@pytest.mark.asyncio
async def test_job_matches_check_constraints(session):
    await _seed(session)
    base = dict(user_id=1, job_id=101, origin="new_job", job_family="software_dev",
                families_version="f1", family_relation="same", location_check="matched")

    session.add(JobMatch(id="jm_ok", status="queued", **base))
    await session.commit()

    bad_rows = [
        dict(id="jm1", status="rated", **{**base, "job_id": 102}),  # rated without tier/resume
        dict(id="jm2", status="rejected", **{**base, "job_id": 102}),  # rejected without code
        dict(id="jm3", status="rejected", reject_code="LOCATION", ai_call_id="aic",
             **{**base, "job_id": 102, "location_check": "rejected"}),  # location reject used LLM
        dict(id="jm4", status="queued", tier="E", **{**base, "job_id": 102}),
        dict(id="jm5", status="queued", **base),  # duplicate user x job
    ]
    for row in bad_rows:
        session.add(JobMatch(**row))
        with pytest.raises(IntegrityError):
            await session.commit()
        await session.rollback()
