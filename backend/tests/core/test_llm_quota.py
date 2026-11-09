"""LLM quota pause: error detection, gateway guard, threshold, watch."""
from unittest.mock import AsyncMock

import pytest

from app.core.llm import quota
from app.core.llm.gateway import AgentGateway
from tests.core.test_llm_providers_and_override import _loaded_agent, _Out


class _StatusError(Exception):
    def __init__(self, message, status_code):
        super().__init__(message)
        self.status_code = status_code


def test_is_quota_error_recognises_exhausted_credit_only():
    key_limit = Exception("Error code: 403 - {'error': {'message': 'Key limit exceeded (total limit). Manage it'}}")
    assert quota.is_quota_error(key_limit)
    assert quota.is_quota_error(_StatusError("Payment required", 402))
    assert quota.is_quota_error(Exception("This request requires more credits, or fewer max_tokens"))
    wrapped = RuntimeError("gateway error")
    wrapped.__cause__ = key_limit
    assert quota.is_quota_error(wrapped)
    assert quota.is_quota_error(quota.QuotaExhaustedError("paused"))

    assert not quota.is_quota_error(_StatusError("Rate limit reached", 429))
    assert not quota.is_quota_error(Exception("Error code: 500 - upstream error"))
    assert not quota.is_quota_error(_StatusError("Forbidden: model not allowed", 403))


def test_below_threshold(monkeypatch):
    monkeypatch.setattr(quota.settings, "LLM_QUOTA_PAUSE_THRESHOLD_USD", 2.0)
    assert quota.below_threshold(quota.KeyStatus(limit=80, limit_remaining=1.5, usage=78.5))
    assert not quota.below_threshold(quota.KeyStatus(limit=80, limit_remaining=29.9, usage=50.1))
    assert not quota.below_threshold(quota.KeyStatus(limit=None, limit_remaining=None, usage=3))  # no key limit


@pytest.mark.asyncio
async def test_gateway_refuses_calls_while_paused(monkeypatch):
    monkeypatch.setattr(quota, "pause_state", lambda: {"reason": "Key limit exceeded"})
    gateway = AgentGateway(loader=AsyncMock())
    gateway._execute_agent = AsyncMock()  # type: ignore[method-assign]
    with pytest.raises(quota.QuotaExhaustedError, match="paused"):
        await gateway.call("demo", "input")
    gateway._execute_agent.assert_not_awaited()
    gateway.loader.load_agent.assert_not_awaited()


@pytest.mark.asyncio
async def test_gateway_pauses_on_quota_error_and_raises_quota_exhausted(monkeypatch):
    paused = []
    monkeypatch.setattr(quota, "pause", lambda reason, source: paused.append((reason, source)))
    gateway = AgentGateway(loader=AsyncMock())
    gateway.loader.load_agent = AsyncMock(return_value=_loaded_agent())
    gateway._execute_agent = AsyncMock(side_effect=Exception("Error code: 403 - Key limit exceeded (total limit)"))  # type: ignore[method-assign]
    gateway._record_ai_call = AsyncMock(return_value=None)  # type: ignore[method-assign]
    with pytest.raises(quota.QuotaExhaustedError):
        await gateway.call("demo", "input")
    assert paused and paused[0][1] == "gateway:demo"

    # Ordinary failures pass through untouched and do not pause.
    paused.clear()
    gateway._execute_agent = AsyncMock(side_effect=ValueError("bad output"))  # type: ignore[method-assign]
    with pytest.raises(ValueError):
        await gateway.call("demo", "input")
    assert paused == []


@pytest.mark.asyncio
async def test_gateway_records_calls_without_task_id():
    gateway = AgentGateway(loader=AsyncMock())
    gateway.loader.load_agent = AsyncMock(return_value=_loaded_agent())
    gateway._execute_agent = AsyncMock(return_value=(_Out(value="ok"), None))  # type: ignore[method-assign]
    recorded = []

    async def fake_create(db, **kwargs):
        recorded.append(kwargs)

        class _Row:
            id = "aic_1"
        return _Row()

    import app.core.llm.gateway as gateway_module

    original = gateway_module.AICallRepository.create
    gateway_module.AICallRepository.create = fake_create
    try:
        class _FakeSession:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc):
                return False

            async def commit(self):
                pass

        original_factory = gateway_module.async_session_factory
        gateway_module.async_session_factory = lambda: _FakeSession()
        context = {"operation": "match_judge", "user_id": 1}
        await gateway.call("demo", "input", context=context)
    finally:
        gateway_module.AICallRepository.create = original
        gateway_module.async_session_factory = original_factory
    assert recorded and recorded[0]["task_id"] is None and recorded[0]["user_id"] == 1
    assert context["ai_call_id"] == "aic_1"


@pytest.mark.asyncio
async def test_watch_quota_pauses_low_and_resumes_when_credit_is_back(monkeypatch):
    from app.modules.workflow import tasks as workflow_tasks

    state = {"paused": None}
    monkeypatch.setattr(quota, "pause_state", lambda: state["paused"])
    monkeypatch.setattr(quota, "pause", lambda reason, source: state.update(paused={"reason": reason}))
    resumed = AsyncMock(return_value={"resubmitted": 3, "in_broker": 0, "skipped_failed": 0, "errors": 0})
    monkeypatch.setattr(workflow_tasks, "resume_llm_work", resumed)

    monkeypatch.setattr(quota, "fetch_openrouter_key_status",
                        lambda: quota.KeyStatus(limit=80, limit_remaining=1.2, usage=78.8))
    assert (await workflow_tasks.watch_quota(db=None))["status"] == "paused"
    assert "$1.20 left" in state["paused"]["reason"]
    resumed.assert_not_awaited()

    monkeypatch.setattr(quota, "fetch_openrouter_key_status",
                        lambda: quota.KeyStatus(limit=120, limit_remaining=41.2, usage=78.8))
    result = await workflow_tasks.watch_quota(db=None)
    assert result["status"] == "resumed" and result["resubmitted"] == 3

    state["paused"] = None
    assert (await workflow_tasks.watch_quota(db=None))["status"] == "ok"
    monkeypatch.setattr(quota, "fetch_openrouter_key_status", lambda: None)
    assert (await workflow_tasks.watch_quota(db=None))["status"] == "unknown"
