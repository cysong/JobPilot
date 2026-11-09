"""LLM quota pause: stop spending (and failing) when the provider is out of credit.

When OpenRouter reports an exhausted key or account (403 "Key limit exceeded",
402 "insufficient credits"), or the remaining key limit falls below
``LLM_QUOTA_PAUSE_THRESHOLD_USD``, a pause flag is set in Redis. While it is set:

- the gateway refuses LLM calls (``QuotaExhaustedError``) without hitting the API;
- workflow tasks park themselves (back to PENDING, no retry consumed);
- new workflow submissions are recorded but not dispatched;
- periodic LLM jobs skip their run; matching keeps its queue untouched.

``llm_quota_watch`` (beat) clears the flag once the balance is back and resubmits
parked work. Redis has no persistence: losing the flag only costs one more failed
call, which sets it again.
"""
from __future__ import annotations

import json
import logging
import time
import urllib.request
from dataclasses import dataclass
from typing import Any, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

PAUSE_KEY = "jobpilot:llm-paused"
OPENROUTER_KEY_URL = "https://openrouter.ai/api/v1/key"

_QUOTA_MARKERS = (
    "key limit exceeded",
    "insufficient credits",
    "requires more credits",
    "credit limit",
    "out of credits",
)


class QuotaExhaustedError(RuntimeError):
    """The LLM provider has no credit left (or calls are paused for that reason)."""


def is_quota_error(exc: BaseException) -> bool:
    """True for provider errors that mean "no credit", not a transient failure."""
    seen: set[int] = set()
    current: Optional[BaseException] = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, QuotaExhaustedError):
            return True
        status = getattr(current, "status_code", None)
        message = str(current).lower()
        if status == 402 or "error code: 402" in message:
            return True
        if any(marker in message for marker in _QUOTA_MARKERS):
            return True
        current = current.__cause__ or current.__context__
    return False


_client = None


def _redis():
    # Checked before every LLM call: keep one client (it pools connections).
    global _client
    if _client is None:
        import redis

        _client = redis.Redis.from_url(settings.REDIS_URL, socket_timeout=2, socket_connect_timeout=2)
    return _client


def pause_state() -> Optional[dict[str, Any]]:
    """The current pause record, or None when LLM calls are allowed."""
    try:
        raw = _redis().get(PAUSE_KEY)
    except Exception as exc:  # noqa: BLE001 - never block work because Redis is unreachable
        logger.warning("llm_pause_state_unavailable err=%s", exc)
        return None
    if not raw:
        return None
    try:
        return json.loads(raw)
    except ValueError:
        return {"reason": raw.decode(errors="replace") if isinstance(raw, bytes) else str(raw)}


def is_paused() -> bool:
    return pause_state() is not None


def pause(reason: str, *, source: str) -> None:
    """Set the pause flag (idempotent: keeps the first reason and time)."""
    record = json.dumps({"reason": reason[:500], "source": source, "since": int(time.time())})
    try:
        if _redis().set(PAUSE_KEY, record, nx=True):
            logger.error("llm_quota_paused source=%s reason=%s", source, reason[:200])
    except Exception as exc:  # noqa: BLE001
        logger.error("llm_pause_set_failed err=%s", exc)


def resume() -> bool:
    """Clear the pause flag. Returns True when it was set."""
    try:
        return bool(_redis().delete(PAUSE_KEY))
    except Exception as exc:  # noqa: BLE001
        logger.error("llm_pause_clear_failed err=%s", exc)
        return False


@dataclass(frozen=True)
class KeyStatus:
    limit: Optional[float]           # None = no key limit
    limit_remaining: Optional[float]
    usage: Optional[float]


def fetch_openrouter_key_status(timeout: float = 15) -> Optional[KeyStatus]:
    """Limit and usage of the configured OpenRouter key (free endpoint). None when
    no key is configured or the request fails."""
    api_key = getattr(settings, "OPENROUTER_API_KEY", None)
    if not api_key:
        return None
    request = urllib.request.Request(OPENROUTER_KEY_URL, headers={"Authorization": f"Bearer {api_key}"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.load(response).get("data") or {}
    except Exception as exc:  # noqa: BLE001
        logger.warning("openrouter_key_status_failed err=%s", exc)
        return None
    return KeyStatus(limit=data.get("limit"), limit_remaining=data.get("limit_remaining"), usage=data.get("usage"))


def below_threshold(status: KeyStatus) -> bool:
    return status.limit_remaining is not None and status.limit_remaining < settings.LLM_QUOTA_PAUSE_THRESHOLD_USD
