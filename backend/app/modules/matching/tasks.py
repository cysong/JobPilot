"""Periodic Celery tasks for matching v3 (docs/job_matching_v3_design.md §10.1).

All three are no-ops unless MATCH_V3_ENABLED is true. They run on beat and are not
retried by Celery: the next tick picks up whatever is left.
"""
from __future__ import annotations

import time

import structlog

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.database import async_session_factory
from app.core.metrics import title_classify_total
from app.core.llm import availability
from app.core.llm.gateway import AgentGateway
from app.modules.matching.families.classifier import classify_missing_titles, resolve_pending_jobs
from app.modules.matching.pipeline import discover_new_jobs, enqueue_matches, judge_queued_matches
from app.modules.workflow import AsyncBaseTask

logger = structlog.get_logger()

_PERIODIC = {"base": AsyncBaseTask, "bind": True, "ignore_result": True, "autoretry_for": (), "max_retries": 0}


def _disabled() -> dict | None:
    return None if settings.MATCH_V3_ENABLED else {"status": "disabled"}


def _paused() -> dict | None:
    """LLM work waits while it is paused (app.core.llm.availability)."""
    return {"status": "paused"} if availability.is_paused() else None


@celery_app.task(**_PERIODIC)
async def discover_new_jobs_task(self) -> dict:
    """Every 5 minutes: register live jobs without a role family row."""
    if (skipped := _disabled()) is not None:
        return skipped
    async with self.session() as db:
        added = await discover_new_jobs(db)
    logger.info("match_discover_completed", added=added)
    return {"added": added}


@celery_app.task(**_PERIODIC)
async def classify_pending_titles_task(self) -> dict:
    """Every 5 minutes: classify new titles, settle pending jobs, queue matches."""
    if (skipped := _disabled() or _paused()) is not None:
        return skipped
    started = time.perf_counter()
    gateway = AgentGateway.get()
    # The classifier functions commit before each model call (no connection held).
    async with self.session() as db:
        titles = await classify_missing_titles(db, gateway)
        resolved = await resolve_pending_jobs(db, gateway, limit=settings.MATCH_JD_READ_LIMIT)
        for outcome, count in resolved.items():
            if count:
                title_classify_total.labels(outcome=outcome).inc(count)
        enqueued = await enqueue_matches(db)
    result = {"titles": titles, "resolved": resolved, "enqueued": enqueued,
              "elapsed_ms": int((time.perf_counter() - started) * 1000)}
    logger.info("match_classify_completed", **result)
    return result


@celery_app.task(**_PERIODIC)
async def judge_queued_matches_task(self) -> dict:
    """Every 2 minutes: judge queued and due retry rows, newest jobs first."""
    if (skipped := _disabled() or _paused()) is not None:
        return skipped
    result = await judge_queued_matches(async_session_factory, AgentGateway.get())
    logger.info("match_judge_completed", **result)
    return result
