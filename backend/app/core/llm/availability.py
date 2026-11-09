"""LLM availability: pause LLM work when retrying cannot help.

Kinds of pause (``LLMUnavailableError.kind``):

- ``quota``  out of credit (402, 403 "Key limit exceeded", or the OpenRouter key
             has less than ``LLM_QUOTA_PAUSE_THRESHOLD_USD`` left)    -> global
- ``auth``   API key rejected (401)                                    -> global
- ``model``  model removed or unknown (404 "model not found / no longer
             available", "No endpoints found")                         -> that model only
- ``outage`` provider down: 5xx / overloaded / timeout / connection errors,
             ``LLM_OUTAGE_FAILURE_THRESHOLD`` in a row within the window
             (circuit breaker, expires after a growing cooldown)       -> global

While a pause is active the gateway refuses matching calls without contacting the
provider, workflow tasks park themselves (PENDING, no retry consumed), new
submissions are recorded but not dispatched, and periodic LLM jobs skip their run.
``llm_availability_watch`` clears quota/auth pauses when the key works again and
model pauses when the model is no longer configured, then resubmits parked work.
Outage pauses expire on their own; the first call after expiry is the probe.

State lives in Redis (no persistence): losing it costs at most one more failure.
"""
from __future__ import annotations

import json
import logging
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

QUOTA, AUTH, MODEL, OUTAGE = "quota", "auth", "model", "outage"
GLOBAL = "global"
PAUSE_PREFIX = "jobpilot:llm-pause:"
OUTAGE_FAILURES_KEY = "jobpilot:llm-outage:failures"
OUTAGE_LEVEL_KEY = "jobpilot:llm-outage:level"
OPENROUTER_KEY_URL = "https://openrouter.ai/api/v1/key"

_QUOTA_MARKERS = ("key limit exceeded", "insufficient credits", "requires more credits", "credit limit",
                  "out of credits")
_MODEL_MARKERS = ("no longer available", "model not found", "is not a valid model", "no endpoints found",
                  "does not exist")
_OUTAGE_MARKERS = ("overloaded", "service unavailable", "bad gateway", "gateway timeout", "upstream error",
                   "connection error", "connection reset", "timed out")
_OUTAGE_STATUSES = {500, 502, 503, 504, 520, 522, 524, 529}
_OUTAGE_CLASS_NAMES = ("Timeout", "APIConnectionError", "ConnectError", "RemoteProtocolError")


class LLMUnavailableError(RuntimeError):
    """LLM calls cannot succeed right now (see module docstring); not a task failure."""

    def __init__(self, message: str, *, kind: str, scope: str = GLOBAL):
        super().__init__(message)
        self.kind = kind
        self.scope = scope


def model_scope(model: str) -> str:
    return f"model={model}"


# ------------------------------------------------------------------ classification


def _chain(exc: BaseException):
    seen: set[int] = set()
    current: Optional[BaseException] = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        yield current
        current = current.__cause__ or current.__context__


def _status(exc: BaseException) -> Optional[int]:
    status = getattr(exc, "status_code", None)
    if isinstance(status, int):
        return status
    match = re.search(r"error code: (\d{3})", str(exc).lower())
    return int(match.group(1)) if match else None


def classify_error(exc: BaseException) -> Optional[str]:
    """The pause kind an LLM error calls for, or None for errors the task's own retry
    (or failure) should handle: rate limits, bad requests, moderation, output parsing."""
    for current in _chain(exc):
        if isinstance(current, LLMUnavailableError):
            return current.kind
        status = _status(current)
        message = str(current).lower()
        if status == 402 or any(marker in message for marker in _QUOTA_MARKERS):
            return QUOTA
        if status == 401 or type(current).__name__ == "AuthenticationError":
            return AUTH
        if (status == 404 or type(current).__name__ == "NotFoundError") and any(
                marker in message for marker in _MODEL_MARKERS):
            return MODEL
        if status in _OUTAGE_STATUSES or any(name in type(current).__name__ for name in _OUTAGE_CLASS_NAMES) \
                or any(marker in message for marker in _OUTAGE_MARKERS):
            return OUTAGE
    return None


def unavailable_cause(exc: BaseException) -> Optional[LLMUnavailableError]:
    """The ``LLMUnavailableError`` in ``exc``'s chain, if LLM work is paused."""
    return next((current for current in _chain(exc) if isinstance(current, LLMUnavailableError)), None)


def is_unavailable(exc: BaseException) -> bool:
    """True when ``exc`` (or its cause) says LLM work is paused."""
    return unavailable_cause(exc) is not None


# ------------------------------------------------------------------ pause state

_client = None


def _redis():
    # Checked around every LLM call: keep one client (it pools connections).
    global _client
    if _client is None:
        import redis

        _client = redis.Redis.from_url(settings.REDIS_URL, socket_timeout=2, socket_connect_timeout=2)
    return _client


def _decode(raw) -> Optional[dict[str, Any]]:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except ValueError:
        return {"kind": "unknown", "reason": raw.decode(errors="replace") if isinstance(raw, bytes) else str(raw)}


def blocking_pause(model: Optional[str]) -> Optional[dict[str, Any]]:
    """The pause that blocks a call to ``model`` (global first), with its scope."""
    keys = [PAUSE_PREFIX + GLOBAL] + ([PAUSE_PREFIX + model_scope(model)] if model else [])
    try:
        values = _redis().mget(keys)
    except Exception as exc:  # noqa: BLE001 - never block work because Redis is unreachable
        logger.warning("llm_pause_state_unavailable err=%s", exc)
        return None
    for key, raw in zip(keys, values):
        record = _decode(raw)
        if record:
            return {**record, "scope": key[len(PAUSE_PREFIX):]}
    return None


def global_pause() -> Optional[dict[str, Any]]:
    """The global pause record (submissions and periodic LLM jobs wait on it)."""
    return blocking_pause(None)


def is_paused() -> bool:
    return global_pause() is not None


def active_pauses() -> dict[str, dict[str, Any]]:
    """Every active pause by scope (``global`` or ``model=<id>``)."""
    pauses: dict[str, dict[str, Any]] = {}
    try:
        client = _redis()
        for key in client.scan_iter(match=PAUSE_PREFIX + "*"):
            key = key.decode() if isinstance(key, bytes) else key
            record = _decode(client.get(key))
            if record:
                ttl = client.ttl(key)
                pauses[key[len(PAUSE_PREFIX):]] = {**record, "expires_in": ttl if ttl and ttl > 0 else None}
    except Exception as exc:  # noqa: BLE001
        logger.warning("llm_pause_list_failed err=%s", exc)
    return pauses


def pause(kind: str, reason: str, *, source: str, scope: str = GLOBAL, ttl: Optional[int] = None) -> bool:
    """Set a pause (keeps an existing one for the same scope). Returns True when set now."""
    record = json.dumps({"kind": kind, "reason": reason[:500], "source": source, "since": int(time.time())})
    try:
        created = bool(_redis().set(PAUSE_PREFIX + scope, record, nx=True, ex=ttl))
    except Exception as exc:  # noqa: BLE001
        logger.error("llm_pause_set_failed err=%s", exc)
        return False
    if created:
        logger.error("llm_paused kind=%s scope=%s ttl=%s source=%s reason=%s", kind, scope, ttl, source, reason[:200])
    return created


def clear(scope: Optional[str] = None) -> list[str]:
    """Clear one pause, or every pause when ``scope`` is None. Returns cleared scopes."""
    scopes = [scope] if scope else list(active_pauses())
    cleared = []
    try:
        for item in scopes:
            if _redis().delete(PAUSE_PREFIX + item):
                cleared.append(item)
    except Exception as exc:  # noqa: BLE001
        logger.error("llm_pause_clear_failed err=%s", exc)
    return cleared


# ------------------------------------------------------------------ outage breaker


def record_success() -> None:
    """A call went through: the provider is up, reset the breaker."""
    try:
        _redis().delete(OUTAGE_FAILURES_KEY, OUTAGE_LEVEL_KEY)
    except Exception:  # noqa: BLE001
        pass


def record_outage_failure(reason: str, *, source: str) -> Optional[int]:
    """Count an outage-type failure; open the breaker when the threshold is reached.

    Returns the cooldown in seconds when the breaker opened. Right after a cooldown
    (``OUTAGE_LEVEL_KEY`` still set) a single failure reopens it, for longer.
    """
    try:
        client = _redis()
        level = int(client.get(OUTAGE_LEVEL_KEY) or 0)
        threshold = 1 if level else settings.LLM_OUTAGE_FAILURE_THRESHOLD
        failures = client.incr(OUTAGE_FAILURES_KEY)
        if failures == 1:
            client.expire(OUTAGE_FAILURES_KEY, settings.LLM_OUTAGE_WINDOW_SECONDS)
        if failures < threshold:
            return None
        level = client.incr(OUTAGE_LEVEL_KEY)
        cooldown = min(settings.LLM_OUTAGE_COOLDOWN_SECONDS * 2 ** (level - 1),
                       settings.LLM_OUTAGE_MAX_COOLDOWN_SECONDS)
        # The level outlives the cooldown so the probe after it reopens on one failure.
        client.expire(OUTAGE_LEVEL_KEY, cooldown + settings.LLM_OUTAGE_WINDOW_SECONDS * 5)
        client.delete(OUTAGE_FAILURES_KEY)
    except Exception as exc:  # noqa: BLE001
        logger.error("llm_outage_breaker_failed err=%s", exc)
        return None
    pause(OUTAGE, f"{failures} consecutive provider failures: {reason}", source=source, ttl=cooldown)
    return cooldown


# ------------------------------------------------------------------ parked work

PARKED_PREFIXES = ("Paused: LLM unavailable", "Waiting: LLM unavailable")
_SCOPE_RE = re.compile(r"\[([^\]]+)\]")


def parked_message(scope: str, kind: str, *, waiting: bool = False) -> str:
    verb = "Waiting: LLM unavailable" if waiting else "Paused: LLM unavailable"
    return f"{verb} [{scope}] ({kind}), resumes automatically"


def parked_scope(error_message: Optional[str]) -> Optional[str]:
    """Scope a parked task waits on, or None when the task is not parked."""
    if not error_message or not error_message.startswith(PARKED_PREFIXES):
        return None
    match = _SCOPE_RE.search(error_message)
    return match.group(1) if match else GLOBAL


# ------------------------------------------------------------------ OpenRouter key probe


@dataclass(frozen=True)
class KeyStatus:
    auth_ok: bool
    limit: Optional[float] = None            # None = no key limit
    limit_remaining: Optional[float] = None
    usage: Optional[float] = None


def fetch_openrouter_key_status(timeout: float = 15) -> Optional[KeyStatus]:
    """Limit and usage of the configured OpenRouter key (free endpoint). ``auth_ok``
    is False when the key is rejected; None when unknown (no key, network error)."""
    api_key = getattr(settings, "OPENROUTER_API_KEY", None)
    if not api_key:
        return None
    request = urllib.request.Request(OPENROUTER_KEY_URL, headers={"Authorization": f"Bearer {api_key}"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.load(response).get("data") or {}
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            return KeyStatus(auth_ok=False)
        logger.warning("openrouter_key_status_failed status=%s", exc.code)
        return None
    except Exception as exc:  # noqa: BLE001
        logger.warning("openrouter_key_status_failed err=%s", exc)
        return None
    return KeyStatus(auth_ok=True, limit=data.get("limit"), limit_remaining=data.get("limit_remaining"),
                     usage=data.get("usage"))


def below_threshold(status: KeyStatus) -> bool:
    return status.limit_remaining is not None and status.limit_remaining < settings.LLM_QUOTA_PAUSE_THRESHOLD_USD
