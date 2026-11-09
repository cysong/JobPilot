"""Admin controls for the LLM quota pause (app.core.llm.quota)."""
import asyncio
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.llm import quota
from app.modules.admin.dependencies import require_admin

router = APIRouter(prefix="/admin/llm/quota", tags=["admin"], dependencies=[Depends(require_admin)])


class LLMQuotaStatus(BaseModel):
    paused: bool
    reason: Optional[str] = None
    source: Optional[str] = None
    since: Optional[int] = None  # unix seconds
    threshold_usd: float
    key_limit: Optional[float] = None
    key_remaining: Optional[float] = None
    key_usage: Optional[float] = None


class LLMQuotaResumeResponse(BaseModel):
    resubmitted: int
    in_broker: int
    skipped_failed: int
    errors: int


async def _status() -> LLMQuotaStatus:
    state = quota.pause_state() or {}
    key = await asyncio.to_thread(quota.fetch_openrouter_key_status)
    return LLMQuotaStatus(
        paused=bool(state), reason=state.get("reason"), source=state.get("source"), since=state.get("since"),
        threshold_usd=settings.LLM_QUOTA_PAUSE_THRESHOLD_USD,
        key_limit=key.limit if key else None, key_remaining=key.limit_remaining if key else None,
        key_usage=key.usage if key else None,
    )


@router.get("", response_model=LLMQuotaStatus)
async def get_llm_quota():
    """Pause flag plus the OpenRouter key's limit and usage."""
    return await _status()


@router.post("/pause", response_model=LLMQuotaStatus)
async def pause_llm_work():
    """Pause LLM work by hand (e.g. before topping up)."""
    quota.pause("Paused by an admin", source="admin")
    return await _status()


@router.post("/resume", response_model=LLMQuotaResumeResponse)
async def resume_llm_work(db: AsyncSession = Depends(get_db)):
    """Clear the pause and resubmit workflows parked while it was set."""
    from app.modules.workflow.tasks import resume_llm_work as _resume

    return LLMQuotaResumeResponse(**(await _resume(db)))
