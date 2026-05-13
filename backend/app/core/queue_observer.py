"""Background observer that publishes Celery queue lengths as a Prometheus gauge.

Runs in the FastAPI process (via lifespan) rather than the Celery worker so the
gauge is exposed on the existing ``/metrics`` endpoint without needing a
worker-side HTTP server. The observer reads Redis ``LLEN <queue>`` directly —
this works because Celery's Redis broker stores pending messages as lists keyed
by queue name.
"""
from __future__ import annotations

import asyncio
import logging

from redis import asyncio as aioredis

from app.core.config import settings
from app.core.metrics import celery_queue_length

logger = logging.getLogger(__name__)

# Queues to monitor. Extend this list if custom Celery queues are introduced.
CELERY_QUEUES: tuple[str, ...] = ("celery",)


async def observe_queue_lengths(interval_seconds: int = 30) -> None:
    """Poll Redis for Celery queue lengths until cancelled."""
    redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        while True:
            for queue in CELERY_QUEUES:
                try:
                    length = await redis.llen(queue)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("queue_observer_llen_failed queue=%s err=%s", queue, exc)
                    continue
                celery_queue_length.labels(queue_name=queue).set(length)
            await asyncio.sleep(interval_seconds)
    finally:
        await redis.aclose()
