"""Quota pause on a real Postgres: parked tasks, parked submissions, resume, matching."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from celery.exceptions import Ignore
from sqlalchemy import select

from tests.modules.matching.conftest import LOCAL_DB, requires_db, session, session_factory  # noqa: F401

pytestmark = requires_db

if LOCAL_DB:
    from app.core.llm import quota
    from app.modules.matching.models import JobMatch
    from app.modules.matching.pipeline import enqueue_matches, judge_queued_matches
    from app.modules.workflow import tasks_base
    from app.modules.workflow.models import TaskExecution
    from app.modules.workflow.reconcile import reconcile_unfinished_tasks
    from app.modules.workflow.service import TaskService
    from app.shared.enums import TaskStatus, TaskType
    from tests.modules.matching.test_pipeline import _classify, _gateway, _seed

from datetime import datetime, timedelta, timezone


def _row(workflow, step, status, *, error=None, total=2):
    return TaskExecution(id=f"{workflow}-{step}", workflow_id=workflow, entity_type="application", entity_id="a1",
                         task_name="t", task_type="resume_tailoring", status=status, step=step, total_steps=total,
                         input_data={}, error_message=error)


@pytest.mark.asyncio
async def test_task_parks_itself_back_to_pending(session_factory, monkeypatch):  # noqa: F811
    monkeypatch.setattr(tasks_base, "async_session_factory", session_factory)
    async with session_factory() as db:
        row = _row("w1", 1, TaskStatus.RUNNING)
        db.add(row)
        await db.commit()

    class Probe(tasks_base.DBTrackingTask):
        name = "tests.quota_probe"

    with pytest.raises(Ignore):
        await Probe()._on_quota_exhausted(quota.QuotaExhaustedError("Key limit exceeded"), {"task_id": "w1-1"})
    async with session_factory() as db:
        parked = await db.get(TaskExecution, "w1-1")
        assert parked.status == TaskStatus.PENDING and parked.error_message.startswith("Paused: LLM quota")


@pytest.mark.asyncio
async def test_submissions_are_recorded_but_not_dispatched_while_paused(session, monkeypatch):  # noqa: F811
    monkeypatch.setattr(quota, "pause_state", lambda: {"reason": "Key limit exceeded"})
    task = await TaskService.submit_task(session, task_type=TaskType.JOB_ANALYSIS, entity_id="1",
                                         input_data={"job_id": 1})
    assert task.status == TaskStatus.PENDING and task.celery_task_id is None
    assert task.error_message.startswith("Waiting: LLM quota")


@pytest.mark.asyncio
async def test_resume_resubmits_only_parked_workflows(session):  # noqa: F811
    session.add_all([
        _row("parked", 1, TaskStatus.PENDING, error="Paused: LLM quota exhausted, resumes automatically"),
        _row("parked", 2, TaskStatus.PENDING),
        _row("waiting", 1, TaskStatus.PENDING, error="Waiting: LLM quota exhausted, starts automatically", total=1),
        _row("live", 1, TaskStatus.RUNNING, total=1),  # running right now: must not be duplicated
        _row("plain", 1, TaskStatus.PENDING, total=1),
    ])
    await session.commit()
    calls = []

    async def resubmit(db, tasks):
        calls.append([t.id for t in tasks])

    await reconcile_unfinished_tasks(
        session, broker_ids=set(), started_before=datetime.now(timezone.utc) + timedelta(seconds=5),
        lookback=timedelta(hours=72), resubmit=resubmit, only_parked=True)
    assert sorted(calls) == [["parked-1", "parked-2"], ["waiting-1"]]


@pytest.mark.asyncio
async def test_judging_does_not_burn_attempts_when_out_of_credit(session_factory):  # noqa: F811
    calls: list = []
    gateway = _gateway(calls)
    async with session_factory() as db:
        await _seed(db, qa_family="qa_test")
        await _classify(db, gateway)
        await enqueue_matches(db)

    async def broke(agent_id, input_data, context=None, model_override=None):
        calls.append(agent_id)
        raise Exception("Error code: 403 - {'error': {'message': 'Key limit exceeded (total limit)'}}")

    out_of_credit = AsyncMock()
    out_of_credit.call = AsyncMock(side_effect=broke)
    stats = await judge_queued_matches(session_factory, out_of_credit)
    assert stats.get("paused", 0) >= 1
    async with session_factory() as db:
        rows = list((await db.execute(select(JobMatch))).scalars())
    queued = [r for r in rows if r.status == "queued"]
    assert len(queued) == 3  # nothing moved to failed_retryable / failed_final
    assert all(r.attempts == 0 and r.next_attempt_at is None and r.judged_at is None for r in queued)
