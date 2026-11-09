"""LLM availability: error classification, gateway handling, circuit breaker, watch."""
import fnmatch
from unittest.mock import AsyncMock

import pytest

from app.core.llm import availability
from app.core.llm.gateway import AgentGateway
from tests.core.test_llm_providers_and_override import _loaded_agent, _Out


class _StatusError(Exception):
    def __init__(self, message, status_code):
        super().__init__(message)
        self.status_code = status_code


class APITimeoutError(Exception):
    pass


class AuthenticationError(Exception):
    pass


@pytest.mark.parametrize("exc, kind", [
    (Exception("Error code: 403 - {'error': {'message': 'Key limit exceeded (total limit)'}}"), "quota"),
    (_StatusError("Payment required", 402), "quota"),
    (Exception("This request requires more credits, or fewer max_tokens"), "quota"),
    (_StatusError("No auth credentials found", 401), "auth"),
    (AuthenticationError("Incorrect API key provided"), "auth"),
    (Exception("Error code: 404 - {'error': {'message': 'The model \"MiniMax-M2.5\" is no longer available.'}}"),
     "model"),
    (_StatusError("No endpoints found matching your data policy", 404), "model"),
    (_StatusError("Service Unavailable", 503), "outage"),
    (Exception("Error code: 529 - Overloaded"), "outage"),
    (APITimeoutError("Request timed out."), "outage"),
    (Exception("Connection error."), "outage"),
    (_StatusError("Rate limit reached", 429), None),
    (_StatusError("Input was flagged by moderation", 403), None),
    (Exception("Error code: 400 - context length exceeded"), None),
    (ValueError("Job 12 not found"), None),
])
def test_classify_error(exc, kind):
    assert availability.classify_error(exc) == kind


def test_classify_error_follows_the_cause_chain():
    wrapped = RuntimeError("gateway error")
    wrapped.__cause__ = _StatusError("Payment required", 402)
    assert availability.classify_error(wrapped) == "quota"
    paused = availability.LLMUnavailableError("paused", kind="model", scope="model=x")
    outer = RuntimeError("judge failed")
    outer.__cause__ = paused
    assert availability.unavailable_cause(outer) is paused


def test_parked_message_round_trip():
    message = availability.parked_message("model=z-ai/glm-5.3-flash", "model")
    assert availability.parked_scope(message) == "model=z-ai/glm-5.3-flash"
    assert availability.parked_scope(availability.parked_message("global", "quota", waiting=True)) == "global"
    assert availability.parked_scope("Error code: 500") is None and availability.parked_scope(None) is None


def _gateway(side_effect):
    gateway = AgentGateway(loader=AsyncMock())
    gateway.loader.load_agent = AsyncMock(return_value=_loaded_agent())
    gateway._execute_agent = AsyncMock(side_effect=side_effect)  # type: ignore[method-assign]
    gateway._record_ai_call = AsyncMock(return_value=None)  # type: ignore[method-assign]
    return gateway


@pytest.mark.asyncio
async def test_gateway_refuses_calls_blocked_by_a_pause(monkeypatch):
    seen = []
    monkeypatch.setattr(availability, "blocking_pause",
                        lambda model: seen.append(model) or {"scope": "global", "kind": "quota", "reason": "x"})
    gateway = _gateway(None)
    with pytest.raises(availability.LLMUnavailableError) as info:
        await gateway.call("demo", "input")
    assert info.value.kind == "quota" and info.value.scope == "global"
    gateway._execute_agent.assert_not_awaited()
    assert seen == [_loaded_agent().model]  # checked against the model actually called


@pytest.mark.asyncio
async def test_gateway_pauses_by_kind(monkeypatch):
    paused = []
    monkeypatch.setattr(availability, "pause",
                        lambda kind, reason, source, scope="global", ttl=None: paused.append((kind, scope)))

    with pytest.raises(availability.LLMUnavailableError):
        await _gateway(Exception("Error code: 403 - Key limit exceeded")).call("demo", "input")
    with pytest.raises(availability.LLMUnavailableError) as info:
        await _gateway(_StatusError("model is no longer available", 404)).call("demo", "input")
    assert info.value.scope == f"model={_loaded_agent().model}"
    assert paused == [("quota", "global"), ("model", f"model={_loaded_agent().model}")]


@pytest.mark.asyncio
async def test_gateway_outage_failures_count_until_the_breaker_opens(monkeypatch):
    opened = {"value": None}
    monkeypatch.setattr(availability, "record_outage_failure", lambda reason, source: opened["value"])
    with pytest.raises(_StatusError):  # below threshold: the task's own retry handles it
        await _gateway(_StatusError("Service Unavailable", 503)).call("demo", "input")
    opened["value"] = 300
    with pytest.raises(availability.LLMUnavailableError) as info:
        await _gateway(_StatusError("Service Unavailable", 503)).call("demo", "input")
    assert info.value.kind == "outage"


@pytest.mark.asyncio
async def test_gateway_success_resets_the_breaker(monkeypatch):
    resets = []
    monkeypatch.setattr(availability, "record_success", lambda: resets.append(1))
    gateway = _gateway(None)
    gateway._execute_agent = AsyncMock(return_value=(_Out(value="ok"), None))  # type: ignore[method-assign]
    await gateway.call("demo", "input")
    assert resets == [1]


class FakeRedis:
    """Just enough of redis-py for the availability module."""

    def __init__(self):
        self.data, self.ttls = {}, {}

    def get(self, key):
        return self.data.get(key)

    def mget(self, keys):
        return [self.data.get(k) for k in keys]

    def set(self, key, value, nx=False, ex=None):
        if nx and key in self.data:
            return None
        self.data[key] = value.encode() if isinstance(value, str) else value
        if ex:
            self.ttls[key] = ex
        return True

    def incr(self, key):
        self.data[key] = str(int(self.data.get(key, 0)) + 1).encode()
        return int(self.data[key])

    def expire(self, key, seconds):
        self.ttls[key] = seconds

    def ttl(self, key):
        return self.ttls.get(key, -1)

    def delete(self, *keys):
        return sum(1 for k in keys if self.data.pop(k, None) is not None)

    def scan_iter(self, match):
        return [k.encode() for k in list(self.data) if fnmatch.fnmatch(k, match)]


@pytest.fixture
def fake_redis(monkeypatch):
    redis = FakeRedis()
    monkeypatch.setattr(availability, "_redis", lambda: redis)
    return redis


@pytest.mark.real_availability
def test_circuit_breaker_opens_after_threshold_and_reopens_longer(fake_redis, monkeypatch):
    monkeypatch.setattr(availability.settings, "LLM_OUTAGE_FAILURE_THRESHOLD", 3)
    monkeypatch.setattr(availability.settings, "LLM_OUTAGE_COOLDOWN_SECONDS", 300)
    monkeypatch.setattr(availability.settings, "LLM_OUTAGE_MAX_COOLDOWN_SECONDS", 1000)
    record = availability.record_outage_failure
    assert record("503", source="t") is None and record("503", source="t") is None
    assert record("503", source="t") == 300
    assert availability.global_pause()["kind"] == "outage"
    assert fake_redis.ttls[availability.PAUSE_PREFIX + "global"] == 300

    # Cooldown over (pause expired): the probe fails once -> reopened for longer.
    fake_redis.delete(availability.PAUSE_PREFIX + "global")
    assert record("503", source="t") == 600
    fake_redis.delete(availability.PAUSE_PREFIX + "global")
    assert record("503", source="t") == 1000  # capped

    # A success resets everything: back to the full threshold.
    availability.record_success()
    fake_redis.delete(availability.PAUSE_PREFIX + "global")
    assert record("503", source="t") is None


@pytest.mark.real_availability
@pytest.mark.asyncio
async def test_watch_availability(fake_redis, monkeypatch):
    from app.modules.workflow import tasks as workflow_tasks

    resumed = AsyncMock(return_value={"resubmitted": 0, "in_broker": 0, "skipped_failed": 0, "errors": 0})
    monkeypatch.setattr(workflow_tasks, "resume_parked_work", resumed)
    monkeypatch.setattr(workflow_tasks, "configured_models", lambda: {"openai/gpt-6.1-terra"})

    def key(**kwargs):
        monkeypatch.setattr(availability, "fetch_openrouter_key_status", lambda: availability.KeyStatus(**kwargs))

    key(auth_ok=False)
    await workflow_tasks.watch_availability(db=None)
    assert availability.global_pause()["kind"] == "auth"

    key(auth_ok=True, limit=80, limit_remaining=30, usage=50)
    result = await workflow_tasks.watch_availability(db=None)
    assert result["cleared"] == ["global"] and availability.global_pause() is None

    key(auth_ok=True, limit=80, limit_remaining=1.5, usage=78.5)
    await workflow_tasks.watch_availability(db=None)
    assert availability.global_pause()["kind"] == "quota"

    # Manual and outage pauses are not cleared by a healthy key; model pauses clear
    # once the model is gone from the configuration.
    availability.clear()
    availability.pause("manual", "admin", source="t")
    availability.pause("model", "gone", source="t", scope="model=minimax/MiniMax-M2.5")
    availability.pause("model", "flaky", source="t", scope="model=openai/gpt-6.1-terra")
    key(auth_ok=True, limit=80, limit_remaining=30, usage=50)
    result = await workflow_tasks.watch_availability(db=None)
    assert result["cleared"] == ["model=minimax/MiniMax-M2.5"]
    assert set(availability.active_pauses()) == {"global", "model=openai/gpt-6.1-terra"}
    assert resumed.await_count == 4  # parked work is re-checked on every run
