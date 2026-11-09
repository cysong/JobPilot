"""Workflow tasks hold no DB transaction (no pooled connection) while a model works.

Each task runs its real code against the local Postgres; the fake gateway checks
pg_stat_activity at the moment of every model call.
"""
from __future__ import annotations

import re

import pytest
from sqlalchemy import select

from tests.modules.matching.conftest import DB_URL, LOCAL_DB, requires_db, session_factory  # noqa: F401

pytestmark = requires_db

if LOCAL_DB:
    import asyncpg

    from app.core.metrics import llm_db_held_total
    from app.modules.applications.models import Application
    from app.modules.applications.tasks import cover_letter_generation_task, resume_tailoring_task
    from app.modules.auth.models import User
    from app.modules.jobs.models import JobAnalysis, SeekJob
    from app.modules.jobs.tasks import analyze_job_task
    from app.modules.resumes.models import Document, Resume
    from app.modules.resumes.tasks import analyze_resume_task
    from app.modules.workflow import tasks_base
    from app.shared.enums import ApplicationStatus

RESUME_ANALYSIS = {
    "candidate_name": "Ann Example", "current_title": "SDET", "total_experience_years": 8,
    "location": "Christchurch", "work_right": "Work visa", "technical_skills": [],
    "target_job_titles": [],
}
RESUME_TEXT = "## Experience\n- Senior SDET 2017 - present: built Java/TestNG API test frameworks, CI pipelines"


async def _idle_in_transaction() -> int:
    conn = await asyncpg.connect(DB_URL.replace("postgresql+asyncpg", "postgresql"))
    try:
        return await conn.fetchval(
            "select count(*) from pg_stat_activity where datname = current_database() "
            "and state = 'idle in transaction' and pid <> pg_backend_pid()")
    finally:
        await conn.close()


class CheckingGateway:
    """Records, for every model call, how many connections sit in an open transaction."""

    def __init__(self):
        self.calls: list[tuple[str, int]] = []

    async def call(self, agent_id, input_data, context=None, model_override=None):
        from app.core.database import sessions_in_transaction

        held = await _idle_in_transaction()
        assert not sessions_in_transaction(), f"{agent_id} called inside an open task transaction"
        self.calls.append((agent_id, held))
        return {
            "universal_translator": "中文岗位描述",
            "job_analyzer": {"required_skills": ["Java"], "tech_stack": ["Java"]},
            "resume_analyzer": RESUME_ANALYSIS,
            "resume_tailor": {"content": "# Tailored resume\n- Java API automation"},
            "cover_letter_writer": {"content": "Dear hiring manager, draft."},
            "cover_letter_polisher": {"content": "Dear hiring manager, polished."},
        }[agent_id]


@pytest.fixture
def gateway(monkeypatch, session_factory):  # noqa: F811
    from app.core.llm.gateway import AgentGateway

    fake = CheckingGateway()
    monkeypatch.setattr(AgentGateway, "get", classmethod(lambda cls: fake))
    monkeypatch.setattr(tasks_base, "async_session_factory", session_factory)
    return fake


async def _run(task, **kwargs):
    """Run a Celery task's body on this event loop (as the worker would, minus the thread hop)."""
    return await task._execute(task.run(**kwargs), kwargs)


async def _seed(db):
    db.add(User(id=1, email="u@example.com", hashed_password="x", full_name="U"))
    db.add(SeekJob(id=1, source_id="s1", title="Senior QA Engineer", advertiser_name="Acme",
                   content="<p>Java API automation, CI/CD.</p>"))
    await db.flush()
    db.add(Document(id="doc_src", root_id="doc_src", content=RESUME_TEXT, content_hash="h", created_by=1))
    await db.flush()
    db.add(Resume(id="res1", user_id=1, document_id="doc_src", title="SDET", is_draft=False, is_deleted=False,
                  analysis_result=RESUME_ANALYSIS))
    await db.flush()
    db.add(Application(id="app1", user_id=1, job_id=1, source_resume_id="res1", status=ApplicationStatus.PENDING))
    await db.commit()


def _assert_released(gateway, agents):
    assert [agent for agent, _ in gateway.calls] == agents
    assert [c for c in gateway.calls if c[1]] == [], gateway.calls


@pytest.mark.asyncio
async def test_job_analysis(session_factory, gateway):  # noqa: F811
    async with session_factory() as db:
        await _seed(db)
    result = await _run(analyze_job_task, job_id=1, task_id="t1")
    _assert_released(gateway, ["universal_translator", "job_analyzer"])
    async with session_factory() as db:
        analysis = (await db.execute(select(JobAnalysis).where(JobAnalysis.job_id == 1))).scalar_one()
    assert result["output_data"]["analysis_id"] == analysis.id and analysis.cn_content == "中文岗位描述"


@pytest.mark.asyncio
async def test_resume_analysis(session_factory, gateway):  # noqa: F811
    async with session_factory() as db:
        await _seed(db)
    result = await _run(analyze_resume_task, resume_id="res1", task_id="t2")
    _assert_released(gateway, ["resume_analyzer"])
    assert result["output_data"]["status"] == "completed" and result["output_data"]["is_draft"] is False


@pytest.mark.asyncio
async def test_resume_tailoring_then_cover_letter(session_factory, gateway):  # noqa: F811
    async with session_factory() as db:
        await _seed(db)
    await _run(analyze_job_task, job_id=1, task_id="t1")
    gateway.calls.clear()

    tailored = await _run(resume_tailoring_task, application_id="app1", resume_id="res1", job_id=1,
                          tailoring_level="deep", task_id="t3")
    cover = await _run(cover_letter_generation_task, application_id="app1", task_id="t4")
    _assert_released(gateway, ["resume_tailor", "cover_letter_writer", "cover_letter_polisher"])

    async with session_factory() as db:
        app = await db.get(Application, "app1")
        tailored_doc = await db.get(Document, app.resume_document_id)
        cover_doc = await db.get(Document, app.cover_letter_document_id)
    assert app.status == ApplicationStatus.READY
    assert tailored["output_data"]["resume_document_id"] == tailored_doc.id
    assert tailored_doc.parent_id == "doc_src" and "Tailored resume" in tailored_doc.content
    assert cover["cover_letter_document_id"] == cover_doc.id and cover_doc.content.endswith("polished.")
    assert app.tailoring_progress["steps"]["cover_letter_generation"] == "completed"


@pytest.mark.asyncio
async def test_gateway_reports_a_call_made_inside_a_transaction(session_factory, monkeypatch):  # noqa: F811
    """The real gateway counts violations (it never commits on the caller's behalf)."""
    from unittest.mock import AsyncMock

    from app.core.llm.gateway import AgentGateway
    from tests.core.test_llm_providers_and_override import _loaded_agent, _Out

    monkeypatch.setattr(tasks_base, "async_session_factory", session_factory)

    class Bad(tasks_base.AsyncBaseTask):
        name = "tests.bad"

        async def run(self):
            gateway = AgentGateway(loader=AsyncMock())
            gateway.loader.load_agent = AsyncMock(return_value=_loaded_agent())
            gateway._execute_agent = AsyncMock(return_value=(_Out(value="ok"), None))  # type: ignore[method-assign]
            gateway._record_ai_call = AsyncMock(return_value=None)  # type: ignore[method-assign]
            async with self.session() as db:
                await db.execute(select(SeekJob.id))  # opens a transaction ...
                await gateway.call("demo", "input")   # ... and keeps it during the call
                assert db.in_transaction()  # untouched: no hidden commit

    before = llm_db_held_total.labels(agent_id="demo")._value.get()
    await _run(Bad())
    assert llm_db_held_total.labels(agent_id="demo")._value.get() == before + 1
