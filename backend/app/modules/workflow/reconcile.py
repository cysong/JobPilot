"""Re-dispatch unfinished workflow tasks once when a worker starts.

The Redis broker has no persistence and the worker acknowledges a message before
running it, so a restart (deploy, crash, Redis recreated) can drop queued or
in-flight messages while their ``task_executions`` rows stay PENDING / RUNNING
forever. On startup we resubmit every such workflow from its first unfinished
step, unless one of its messages is still in the broker.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.workflow.models import TaskExecution
from app.shared.enums import TaskStatus

logger = logging.getLogger(__name__)

UNFINISHED = (TaskStatus.PENDING, TaskStatus.RUNNING)
LOCK_KEY = "jobpilot:workflow-reconcile"


@dataclass
class ReconcileResult:
    resubmitted: list[str] = field(default_factory=list)  # workflow ids
    in_broker: list[str] = field(default_factory=list)
    skipped_failed: list[str] = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)

    def summary(self) -> dict[str, int]:
        return {"resubmitted": len(self.resubmitted), "in_broker": len(self.in_broker),
                "skipped_failed": len(self.skipped_failed), "errors": len(self.errors)}


def message_task_ids(raw_messages: Iterable[bytes | str]) -> set[str]:
    """Celery task ids in raw Redis broker entries (queue list items, or ``unacked``
    hash values which wrap the message as ``[message, exchange, routing_key]``)."""
    ids: set[str] = set()
    for raw in raw_messages:
        try:
            data = json.loads(raw)
        except (TypeError, ValueError):
            continue
        if isinstance(data, list) and data:
            data = data[0]
        task_id = (data.get("headers") or {}).get("id") if isinstance(data, dict) else None
        if task_id:
            ids.add(task_id)
    return ids


def broker_task_ids(redis_client, queues: Iterable[str]) -> set[str]:
    """Task ids still waiting in the broker: queued, or delivered but not acknowledged."""
    raw: list[bytes] = []
    for queue in queues:
        raw.extend(redis_client.lrange(queue, 0, -1))
    raw.extend(redis_client.hvals("unacked"))
    return message_task_ids(raw)


async def reconcile_unfinished_tasks(
    db: AsyncSession,
    *,
    broker_ids: set[str],
    started_before: datetime,
    lookback: timedelta,
    resubmit,
) -> ReconcileResult:
    """Resubmit unfinished workflows.

    ``started_before``: rows touched after this instant belong to the worker that is
    starting now and are left alone. ``resubmit(db, tasks)`` dispatches the given
    consecutive steps (``TaskService.resubmit_tasks``).
    """
    result = ReconcileResult()
    workflow_ids = list((await db.execute(
        select(TaskExecution.workflow_id).where(
            TaskExecution.status.in_(UNFINISHED),
            TaskExecution.created_at >= started_before - lookback,
            TaskExecution.updated_at < started_before,
        ).distinct()
    )).scalars())
    for workflow_id in workflow_ids:
        tasks = list((await db.execute(
            select(TaskExecution).where(TaskExecution.workflow_id == workflow_id).order_by(TaskExecution.step)
        )).scalars())
        if any(t.celery_task_id in broker_ids for t in tasks if t.celery_task_id):
            result.in_broker.append(workflow_id)
            continue
        anchor_idx = next((i for i, t in enumerate(tasks) if t.status != TaskStatus.SUCCESS), None)
        if anchor_idx is None:
            continue
        if tasks[anchor_idx].status not in UNFINISHED:
            # A failed step stops its workflow; the steps after it stay PENDING on purpose.
            result.skipped_failed.append(workflow_id)
            continue
        try:
            await resubmit(db, tasks[anchor_idx:])
            result.resubmitted.append(workflow_id)
        except Exception as exc:  # noqa: BLE001 - one bad workflow must not stop the rest
            await db.rollback()
            result.errors[workflow_id] = str(exc)[:300]
            logger.warning("workflow_reconcile_failed workflow_id=%s err=%s", workflow_id, exc)
    return result


def run_startup_reconcile(started_before: datetime | None = None) -> ReconcileResult | None:
    """Entry point for the worker startup hook. Only one worker runs it at a time."""
    import redis

    from app.core.celery_lifecycle import run_coroutine_sync
    from app.core.config import settings
    from app.core.database import async_session_factory
    from app.core.queue_observer import CELERY_QUEUES
    from app.modules.workflow.service import TaskService

    started_before = started_before or datetime.now(timezone.utc)
    client = redis.Redis.from_url(settings.REDIS_URL)
    if not client.set(LOCK_KEY, "1", nx=True, ex=600):
        logger.info("workflow_reconcile_skipped reason=another_worker_running_it")
        return None
    try:
        broker_ids = broker_task_ids(client, CELERY_QUEUES)

        async def _run() -> ReconcileResult:
            async with async_session_factory() as db:
                return await reconcile_unfinished_tasks(
                    db, broker_ids=broker_ids, started_before=started_before,
                    lookback=timedelta(hours=settings.TASK_RECONCILE_LOOKBACK_HOURS),
                    resubmit=TaskService.resubmit_tasks,
                )

        result = run_coroutine_sync(_run())
        logger.info("workflow_reconcile_completed %s", result.summary())
        return result
    finally:
        client.delete(LOCK_KEY)
        client.close()
