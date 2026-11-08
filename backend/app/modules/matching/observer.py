"""Publish matching v3 queue and result gauges from job_matches.

Runs in the API process next to the Celery queue observer, so the gauges are
on the existing /metrics endpoint and reflect the database rather than the
memory of whichever worker last ran.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from app.core.database import async_session_factory
from app.core.metrics import (
    match_judged_24h,
    match_queue_depth,
    match_queue_oldest_age_seconds,
    match_tier_24h,
)
from app.modules.matching.models import JobMatch, JobMatchStatus

logger = logging.getLogger(__name__)

JUDGED_STATUSES = (
    JobMatchStatus.RATED, JobMatchStatus.REJECTED, JobMatchStatus.FAILED_RETRYABLE, JobMatchStatus.FAILED_FINAL,
)
TIERS = ("A", "B", "C", "D")


async def collect_match_gauges(db, *, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    pending = (JobMatchStatus.QUEUED, JobMatchStatus.FAILED_RETRYABLE)
    depth = (await db.execute(
        select(func.count()).where(JobMatch.status.in_(pending))
    )).scalar_one()
    oldest = (await db.execute(
        select(func.min(JobMatch.queued_at)).where(JobMatch.status == JobMatchStatus.QUEUED,
                                                   JobMatch.origin == "new_job")
    )).scalar_one()
    since = now - timedelta(hours=24)
    by_status = dict((await db.execute(
        select(JobMatch.status, func.count()).where(JobMatch.judged_at >= since).group_by(JobMatch.status)
    )).all())
    by_tier = dict((await db.execute(
        select(JobMatch.tier, func.count())
        .where(JobMatch.judged_at >= since, JobMatch.status == JobMatchStatus.RATED)
        .group_by(JobMatch.tier)
    )).all())
    return {
        "depth": depth,
        "oldest_age": (now - oldest).total_seconds() if oldest else 0.0,
        "judged": {s: by_status.get(s, 0) for s in JUDGED_STATUSES},
        "tiers": {t: by_tier.get(t, 0) for t in TIERS},
    }


def publish(values: dict) -> None:
    match_queue_depth.set(values["depth"])
    match_queue_oldest_age_seconds.set(values["oldest_age"])
    for status, count in values["judged"].items():
        match_judged_24h.labels(status=status).set(count)
    for tier, count in values["tiers"].items():
        match_tier_24h.labels(tier=tier).set(count)


async def observe_match_metrics(interval_seconds: int = 60) -> None:
    """Refresh the gauges until cancelled; errors are logged and retried next tick."""
    while True:
        try:
            async with async_session_factory() as db:
                publish(await collect_match_gauges(db))
        except Exception as exc:  # noqa: BLE001
            logger.warning("match_observer_failed err=%s", exc)
        await asyncio.sleep(interval_seconds)
