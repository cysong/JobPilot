"""Periodic workflow maintenance tasks."""
from __future__ import annotations

import asyncio
import logging

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.llm import quota
from app.modules.workflow.tasks_base import AsyncBaseTask

logger = logging.getLogger(__name__)


async def resume_llm_work(db) -> dict:
    """Clear the quota pause and resubmit workflows parked while it was set."""
    from app.modules.workflow.reconcile import reconcile_now

    quota.resume()
    result = await reconcile_now(db, quota._redis(), only_parked=True)
    logger.info("llm_quota_resumed %s", result.summary())
    return result.summary()


async def watch_quota(db) -> dict:
    """Pause LLM work when the OpenRouter key runs low; resume it (and resubmit parked
    workflows) once credit is back."""
    status = await asyncio.to_thread(quota.fetch_openrouter_key_status)
    paused = quota.pause_state()
    if status is None:
        return {"status": "unknown", "paused": bool(paused)}
    if quota.below_threshold(status):
        quota.pause(f"OpenRouter key has ${status.limit_remaining:.2f} left "
                    f"(threshold ${settings.LLM_QUOTA_PAUSE_THRESHOLD_USD:.2f})", source="quota_watch")
        return {"status": "paused", "remaining": status.limit_remaining}
    if paused:
        return {"status": "resumed", "remaining": status.limit_remaining, **(await resume_llm_work(db))}
    return {"status": "ok", "remaining": status.limit_remaining}


@celery_app.task(base=AsyncBaseTask, bind=True, ignore_result=True, autoretry_for=(), max_retries=0)
async def llm_quota_watch(self) -> dict:
    """Every 5 minutes, see ``watch_quota``."""
    return await watch_quota(self.db)
