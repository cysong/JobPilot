"""Background observer that publishes Celery queue lengths as a Prometheus gauge.

Runs in the FastAPI process (via lifespan) rather than the Celery worker so the
gauge is exposed on the existing ``/metrics`` endpoint without needing a
worker-side HTTP server. The observer reads Redis ``LLEN <queue>`` directly —
this works because Celery's Redis broker stores pending messages as lists keyed
by queue name.
"""
from __future__ import annotations

import asyncio
import json
import logging

from redis import asyncio as aioredis

from app.core.config import settings
from app.core.llm.availability import PAUSE_PREFIX
from app.core.metrics import celery_queue_length, llm_paused

logger = logging.getLogger(__name__)

# Queues to monitor. Extend this list if custom Celery queues are introduced.
CELERY_QUEUES: tuple[str, ...] = ("celery",)


async def _publish_llm_pauses(redis) -> None:
    """jobpilot_llm_paused{kind, scope}: 1 per active pause, 0 for kinds now clear."""
    counts: dict[tuple[str, str], int] = {}
    async for key in redis.scan_iter(match=PAUSE_PREFIX + "*"):
        raw = await redis.get(key)
        if not raw:
            continue
        try:
            kind = json.loads(raw).get("kind", "unknown")
        except ValueError:
            kind = "unknown"
        scope = "global" if key.endswith("global") else "model"
        counts[(kind, scope)] = counts.get((kind, scope), 0) + 1
    for kind in ("quota", "auth", "model", "outage", "manual"):
        for scope in ("global", "model"):
            llm_paused.labels(kind=kind, scope=scope).set(counts.get((kind, scope), 0))


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
            try:
                await _publish_llm_pauses(redis)
            except Exception as exc:  # noqa: BLE001
                logger.warning("queue_observer_llm_pause_failed err=%s", exc)
            await asyncio.sleep(interval_seconds)
    finally:
        await redis.aclose()
