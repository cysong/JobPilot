"""Worker startup reconcile, application failure on a failed step, and per-execution sessions."""
from __future__ import annotations

import asyncio
import json
import threading
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select, update

from app.modules.workflow.reconcile import message_task_ids
from tests.modules.matching.conftest import LOCAL_DB, requires_db, session, session_factory  # noqa: F401

if LOCAL_DB:
    from app.modules.applications.models import Application
    from app.modules.auth.models import User
    from app.modules.jobs.models import SeekJob
    from app.modules.resumes.models import Document, Resume
    from app.modules.workflow.models import TaskExecution
    from app.modules.workflow.reconcile import reconcile_unfinished_tasks
    from app.modules.workflow.tasks_base import _fail_workflow_application
    from app.shared.enums import ApplicationStatus, TaskStatus

NOW = datetime.now(timezone.utc)


def test_message_task_ids_reads_queue_items_and_unacked_entries():
    queued = json.dumps({"headers": {"id": "c1", "task": "x"}, "body": "..."})
    unacked = json.dumps([{"headers": {"id": "c2"}}, "", "celery"])
    assert message_task_ids([queued, unacked, b"not json", json.dumps({"no": "headers"})]) == {"c1", "c2"}


def _task(workflow, step, status, *, celery=None, total=3, task_type="resume_tailoring", entity_type="application"):
    return TaskExecution(id=f"{workflow}-{step}", workflow_id=workflow, entity_type=entity_type, entity_id="app1",
                         task_name=task_type, task_type=task_type, status=status, step=step, total_steps=total,
                         celery_task_id=celery, input_data={})


@requires_db
@pytest.mark.asyncio
async def test_reconcile_resubmits_lost_workflows_from_first_unfinished_step(session):  # noqa: F811
    session.add_all([
        # Lost chain: step 1 done, step 2 PENDING with no broker message.
        _task("w_lost", 1, TaskStatus.SUCCESS), _task("w_lost", 2, TaskStatus.PENDING, celery="gone2"),
        _task("w_lost", 3, TaskStatus.PENDING, celery="gone3"),
        # Killed mid-run.
        _task("w_running", 1, TaskStatus.RUNNING, celery="dead", total=1),
        # Still queued in the broker.
        _task("w_queued", 1, TaskStatus.PENDING, celery="alive", total=1),
        # A failed step stops the chain: leave it alone.
        _task("w_failed", 1, TaskStatus.FAILED, total=2), _task("w_failed", 2, TaskStatus.PENDING, total=2),
        # Too old to resurrect.
        _task("w_old", 1, TaskStatus.PENDING, total=1),
    ])
    await session.commit()
    await session.execute(update(TaskExecution).where(TaskExecution.workflow_id == "w_old").values(
        created_at=NOW - timedelta(days=10)))
    await session.commit()

    calls = []

    async def resubmit(db, tasks):
        calls.append([t.id for t in tasks])
        if tasks[0].workflow_id == "w_running":
            raise RuntimeError("broker down")  # one failure must not stop the others

    result = await reconcile_unfinished_tasks(
        session, broker_ids={"alive"}, started_before=datetime.now(timezone.utc) + timedelta(seconds=5),
        lookback=timedelta(hours=72), resubmit=resubmit)

    assert sorted(calls) == [["w_lost-2", "w_lost-3"], ["w_running-1"]]
    assert result.resubmitted == ["w_lost"]
    assert result.in_broker == ["w_queued"] and result.skipped_failed == ["w_failed"]
    assert "w_running" in result.errors


@requires_db
@pytest.mark.asyncio
async def test_reconcile_ignores_rows_touched_by_the_starting_worker(session):  # noqa: F811
    session.add(_task("w_new", 1, TaskStatus.RUNNING, total=1))
    await session.commit()
    calls = []

    async def resubmit(db, tasks):
        calls.append(tasks)

    result = await reconcile_unfinished_tasks(
        session, broker_ids=set(), started_before=NOW - timedelta(minutes=1),
        lookback=timedelta(hours=72), resubmit=resubmit)
    assert calls == [] and result.summary()["resubmitted"] == 0


@requires_db
@pytest.mark.asyncio
async def test_failed_step_marks_owning_application_failed(session):  # noqa: F811
    session.add(User(id=1, email="u@example.com", hashed_password="x", full_name="U"))
    session.add(SeekJob(id=1, source_id="s1", title="Dev", listed_at=NOW))
    await session.flush()
    session.add(Document(id="doc1", root_id="doc1", content="r", content_hash="h", created_by=1))
    await session.flush()
    session.add(Resume(id="res1", user_id=1, document_id="doc1", title="R", is_draft=False, is_deleted=False))
    await session.flush()
    session.add(Application(id="app1", user_id=1, job_id=1, source_resume_id="res1", status=ApplicationStatus.PENDING))
    # In application workflows the job analysis step is typed "job" but shares the workflow.
    failed = _task("w_app", 1, TaskStatus.FAILED, task_type="job_analysis", entity_type="job")
    session.add_all([failed, _task("w_app", 2, TaskStatus.PENDING), _task("w_app", 3, TaskStatus.PENDING)])
    await session.commit()

    await _fail_workflow_application(session, failed, "model is no longer available")
    app = (await session.execute(select(Application).where(Application.id == "app1"))).scalar_one()
    assert app.status == ApplicationStatus.FAILED
    assert "job_analysis failed: model is no longer available" in (app.last_error or "")

    # Already settled applications are left alone.
    app.status = ApplicationStatus.READY
    await session.commit()
    await _fail_workflow_application(session, failed, "again")
    await session.refresh(app)
    assert app.status == ApplicationStatus.READY


def test_concurrent_executions_of_one_task_type_get_their_own_session(monkeypatch):
    """Celery shares one Task instance across threads; each execution must get its own
    sessions and its own tracking of them."""
    from app.core.database import task_sessions
    from app.modules.workflow import tasks_base

    class FakeSession:
        def in_transaction(self):
            return False

    class FakeFactory:
        def __call__(self):
            return self

        async def __aenter__(self):
            return FakeSession()

        async def __aexit__(self, *exc):
            return False

    monkeypatch.setattr(tasks_base, "async_session_factory", FakeFactory())

    class Probe(tasks_base.AsyncBaseTask):
        name = "tests.probe"

        async def run(self, delay):
            async with self.session() as db:
                await asyncio.sleep(delay)  # let the other execution open its own meanwhile
                assert task_sessions.get() == [db]
            assert task_sessions.get() == []
            return id(db)

    task = Probe()
    results, errors = [], []

    def worker(delay):
        try:
            results.append(task(delay))
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(d,)) for d in (0.2, 0.05)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors and len(set(results)) == 2
