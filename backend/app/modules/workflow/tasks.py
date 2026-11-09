"""Periodic workflow maintenance tasks."""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import yaml

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.llm import availability
from app.core.llm.config import llm_gateway_settings
from app.modules.workflow.tasks_base import AsyncBaseTask

logger = logging.getLogger(__name__)


def configured_models() -> set[str]:
    """Models the app can call: every agent config plus the matching overrides."""
    models = {settings.MATCH_JUDGE_MODEL, settings.TITLE_CLASSIFIER_MODEL}
    for path in Path(llm_gateway_settings.AGENT_CONFIG_DIR).glob("*.yaml"):
        try:
            model = (yaml.safe_load(path.read_text()) or {}).get("model")
        except (OSError, yaml.YAMLError):
            continue
        if model:
            models.add(str(model))
    return models


async def resume_parked_work(db) -> dict:
    """Resubmit workflows parked by a pause that has since been cleared."""
    from app.modules.workflow.reconcile import reconcile_now

    blocked = set(availability.active_pauses())
    result = await reconcile_now(db, availability._redis(), only_parked=True, blocked_scopes=blocked)
    if result.resubmitted:
        logger.info("llm_parked_work_resumed %s", result.summary())
    return result.summary()


async def watch_availability(db) -> dict:
    """Re-evaluate LLM pauses, then resubmit parked work whose pause is gone.

    - quota / auth (global): probe the OpenRouter key; pause when it is rejected or
      below the balance threshold, clear when it works again;
    - model: clear once the model is no longer configured (config changed and deployed);
    - outage: expires on its own (TTL); the resubmitted work is the probe.
    """
    pauses = availability.active_pauses()
    cleared: list[str] = []
    key = await asyncio.to_thread(availability.fetch_openrouter_key_status)
    if key is not None:
        current = pauses.get(availability.GLOBAL) or {}
        if not key.auth_ok:
            availability.pause(availability.AUTH, "OpenRouter rejected the API key (401)", source="watch")
        elif availability.below_threshold(key):
            availability.pause(availability.QUOTA, f"OpenRouter key has ${key.limit_remaining:.2f} left "
                               f"(threshold ${settings.LLM_QUOTA_PAUSE_THRESHOLD_USD:.2f})", source="watch")
        elif current.get("kind") in (availability.QUOTA, availability.AUTH):
            cleared += availability.clear(availability.GLOBAL)
    models = configured_models()
    for scope in pauses:
        if scope.startswith("model=") and scope[len("model="):] not in models:
            cleared += availability.clear(scope)
    return {"cleared": cleared, "remaining_usd": key.limit_remaining if key else None,
            "paused": sorted(availability.active_pauses()), **(await resume_parked_work(db))}


@celery_app.task(base=AsyncBaseTask, bind=True, ignore_result=True, autoretry_for=(), max_retries=0)
async def llm_availability_watch(self) -> dict:
    """Every 5 minutes, see ``watch_availability``."""
    return await watch_availability(self.db)
