"""Admin controls for LLM pauses (app.core.llm.availability)."""
import asyncio
from typing import Optional

from fastapi import APIRouter, Body, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.llm import availability
from app.modules.admin.dependencies import require_admin

router = APIRouter(prefix="/admin/llm/availability", tags=["admin"], dependencies=[Depends(require_admin)])


class LLMPause(BaseModel):
    scope: str  # "global" or "model=<id>"
    kind: str   # quota | auth | model | outage | manual
    reason: Optional[str] = None
    source: Optional[str] = None
    since: Optional[int] = None       # unix seconds
    expires_in: Optional[int] = None  # seconds, outage pauses only


class LLMAvailability(BaseModel):
    pauses: list[LLMPause]
    threshold_usd: float
    key_ok: Optional[bool] = None
    key_limit: Optional[float] = None
    key_remaining: Optional[float] = None
    key_usage: Optional[float] = None


class LLMResumeResult(BaseModel):
    cleared: list[str]
    resubmitted: int
    in_broker: int
    skipped_failed: int
    errors: int


async def _status() -> LLMAvailability:
    pauses = availability.active_pauses()
    key = await asyncio.to_thread(availability.fetch_openrouter_key_status)
    return LLMAvailability(
        pauses=[LLMPause(scope=scope, kind=p.get("kind", "unknown"), reason=p.get("reason"), source=p.get("source"),
                         since=p.get("since"), expires_in=p.get("expires_in")) for scope, p in sorted(pauses.items())],
        threshold_usd=settings.LLM_QUOTA_PAUSE_THRESHOLD_USD,
        key_ok=key.auth_ok if key else None,
        key_limit=key.limit if key else None, key_remaining=key.limit_remaining if key else None,
        key_usage=key.usage if key else None,
    )


@router.get("", response_model=LLMAvailability)
async def get_llm_availability():
    """Active pauses plus the OpenRouter key's limit and usage."""
    return await _status()


@router.post("/pause", response_model=LLMAvailability)
async def pause_llm_work():
    """Pause all LLM work by hand (e.g. before topping up); cleared only by resume."""
    availability.pause("manual", "Paused by an admin", source="admin")
    return await _status()


@router.post("/resume", response_model=LLMResumeResult)
async def resume_llm_work(
    db: AsyncSession = Depends(get_db),
    scope: Optional[str] = Body(None, embed=True, description="Pause to clear; all when omitted"),
):
    """Clear a pause (or all) and resubmit the work parked on it."""
    from app.modules.workflow.tasks import resume_parked_work

    cleared = availability.clear(scope)
    return LLMResumeResult(cleared=cleared, **(await resume_parked_work(db)))
