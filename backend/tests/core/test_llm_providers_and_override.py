"""Tests for OpenRouter provider wiring and per-call model overrides in AgentGateway."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from agents import Agent
from agents.model_settings import ModelSettings
from pydantic import BaseModel

from app.core.config import settings
from app.core.llm import providers as providers_module
from app.core.llm.gateway import AgentGateway
from app.core.llm.output_schemas import CleaningOutputSchema
from app.core.llm.providers import (
    OPENROUTER_PROVIDER_PREFERENCES,
    build_provider_runtime,
    normalize_provider_name,
)
from app.core.llm.types import ModelOverride


class _Out(BaseModel):
    value: str


def _loaded_agent(*, provider: str = "openai", output_type=_Out) -> Agent:
    """Build an Agent decorated the way AgentLoader decorates it."""
    agent = Agent(
        name="demo",
        instructions="do it",
        model="gpt-5",
        output_type=output_type,
        model_settings=ModelSettings(max_tokens=1000),
    )
    setattr(agent, "agent_id", "demo")
    setattr(agent, "provider", provider)
    setattr(agent, "config_version", 3)
    setattr(agent, "max_turns", 2)
    setattr(
        agent,
        "config_metadata",
        {"agent_id": "demo", "provider": provider, "model": "gpt-5", "model_settings": {"max_tokens": 1000}},
    )
    return agent


# ---------------------------------------------------------------- providers


def test_normalize_provider_accepts_openrouter_case_insensitively():
    assert normalize_provider_name(" OpenRouter ") == "openrouter"


def test_normalize_provider_rejects_unknown():
    with pytest.raises(ValueError):
        normalize_provider_name("anthropic-direct")


def test_openrouter_runtime_uses_chat_completions_and_passthrough_model_ids(monkeypatch):
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "test-key")
    runtime = build_provider_runtime("openrouter")

    assert runtime.provider == "openrouter"
    assert runtime.api_mode == "chat_completions"
    assert runtime.tracing_disabled is True
    # Namespaced ids ("openai/...", "z-ai/...") must reach OpenRouter verbatim.
    assert runtime.model_provider._openai_prefix_mode == "model_id"
    assert runtime.model_provider._unknown_prefix_mode == "model_id"
    assert runtime.default_extra_body == {"provider": OPENROUTER_PROVIDER_PREFERENCES}
    assert OPENROUTER_PROVIDER_PREFERENCES["require_parameters"] is True
    assert OPENROUTER_PROVIDER_PREFERENCES["data_collection"] == "deny"


def test_openrouter_runtime_requires_api_key(monkeypatch):
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "")
    with pytest.raises(ValueError, match="openrouter"):
        build_provider_runtime("openrouter")


def test_openai_runtime_has_no_default_extra_body(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-key")
    assert build_provider_runtime("openai").default_extra_body == {}


def test_runtime_extra_body_is_not_shared_between_calls(monkeypatch):
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "test-key")
    first = build_provider_runtime("openrouter")
    first.default_extra_body["provider"]["require_parameters"] = False
    assert providers_module.OPENROUTER_PROVIDER_PREFERENCES["require_parameters"] is True


# ---------------------------------------------------------------- overrides


def test_model_override_switches_provider_model_and_settings_without_mutating_original():
    agent = _loaded_agent()
    override = ModelOverride(
        provider="openrouter",
        model="openai/gpt-6.1-terra",
        model_settings={"extra_args": {"seed": 7}},
    )

    clone = AgentGateway._apply_model_override(agent, override)

    assert clone.model == "openai/gpt-6.1-terra"
    assert getattr(clone, "provider") == "openrouter"
    assert clone.model_settings.max_tokens == 1000  # kept from YAML
    assert clone.model_settings.extra_args == {"seed": 7}  # merged from override
    # Non-OpenAI providers get the JSON-cleaning output wrapper.
    assert isinstance(clone.output_type, CleaningOutputSchema)
    assert clone.output_type._schema.output_type is _Out
    # Loader attributes survive the clone.
    assert getattr(clone, "agent_id") == "demo"
    assert getattr(clone, "config_version") == 3
    assert getattr(clone, "max_turns") == 2
    meta = getattr(clone, "config_metadata")
    assert meta["model"] == "openai/gpt-6.1-terra"
    assert meta["provider"] == "openrouter"
    assert meta["model_override"] is True
    assert meta["model_settings"] == {"max_tokens": 1000, "extra_args": {"seed": 7}}

    # The shared, cached agent is untouched.
    assert agent.model == "gpt-5"
    assert getattr(agent, "provider") == "openai"
    assert agent.output_type is _Out
    assert "model_override" not in getattr(agent, "config_metadata")


def test_model_override_back_to_openai_unwraps_cleaning_schema():
    agent = _loaded_agent(provider="openrouter", output_type=CleaningOutputSchema(_Out))
    clone = AgentGateway._apply_model_override(agent, ModelOverride(provider="openai", model="gpt-5-mini"))
    assert clone.output_type is _Out
    assert getattr(clone, "provider") == "openai"


def test_model_override_keeps_plain_text_agents_plain():
    agent = _loaded_agent(output_type=None)
    clone = AgentGateway._apply_model_override(agent, ModelOverride(provider="openrouter"))
    assert clone.output_type is None
    assert clone.model == "gpt-5"


def test_default_extra_body_merges_and_agent_values_win():
    agent = _loaded_agent()
    agent.model_settings = ModelSettings(extra_body={"provider": {"order": ["x"]}, "foo": 1})

    merged = AgentGateway._with_default_extra_body(
        agent, {"provider": {"require_parameters": True}, "bar": 2}
    )

    assert merged.model_settings.extra_body == {"provider": {"order": ["x"]}, "foo": 1, "bar": 2}
    assert agent.model_settings.extra_body == {"provider": {"order": ["x"]}, "foo": 1}


def test_cost_uses_openrouter_pricing():
    cost = AgentGateway._calculate_cost("openai/gpt-6.1-terra", 1_000_000, 1_000_000)
    assert cost == pytest.approx(6.0)
    assert AgentGateway._calculate_cost("z-ai/glm-5.3-flash", 1_000_000, 0) == pytest.approx(0.034)


# ---------------------------------------------------------------- call()


@pytest.mark.asyncio
async def test_call_applies_override_and_writes_ai_call_id_back():
    agent = _loaded_agent()
    gateway = AgentGateway(loader=AsyncMock())
    gateway.loader.load_agent = AsyncMock(return_value=agent)
    executed: list[Agent] = []

    async def fake_execute(run_agent, input_data):
        executed.append(run_agent)
        return _Out(value="ok"), None

    gateway._execute_agent = fake_execute  # type: ignore[method-assign]
    gateway._record_ai_call = AsyncMock(return_value="aic_123")  # type: ignore[method-assign]

    context: dict = {"task_id": "task_1"}
    result = await gateway.call(
        "demo",
        "input",
        context=context,
        model_override=ModelOverride(provider="openrouter", model="z-ai/glm-5.3-flash"),
    )

    assert result == _Out(value="ok")
    assert executed[0].model == "z-ai/glm-5.3-flash"
    assert context["ai_call_id"] == "aic_123"
    assert context["usage"] == {
        "model": "z-ai/glm-5.3-flash", "provider": "openrouter",
        "input_tokens": 0, "output_tokens": 0, "estimated_cost": 0.0,
    }
    recorded_agent = gateway._record_ai_call.await_args.kwargs["agent"]
    assert getattr(recorded_agent, "provider") == "openrouter"


@pytest.mark.asyncio
async def test_call_without_recording_leaves_context_without_ai_call_id():
    agent = _loaded_agent()
    gateway = AgentGateway(loader=AsyncMock())
    gateway.loader.load_agent = AsyncMock(return_value=agent)
    gateway._execute_agent = AsyncMock(return_value=(_Out(value="ok"), None))  # type: ignore[method-assign]
    gateway._record_ai_call = AsyncMock(return_value=None)  # type: ignore[method-assign]

    context: dict = {}
    await gateway.call("demo", "input", context=context)

    assert "ai_call_id" not in context
    assert gateway._execute_agent.await_args.args[0] is agent


def test_usage_summary_computes_cost():
    class _Usage:
        input_tokens = 2_000
        output_tokens = 1_000

    agent = AgentGateway._apply_model_override(
        _loaded_agent(), ModelOverride(provider="openrouter", model="openai/gpt-6.1-terra")
    )
    summary = AgentGateway._usage_summary(agent, _Usage())
    assert summary["input_tokens"] == 2_000
    assert summary["estimated_cost"] == pytest.approx(2_000 * 1e-6 + 1_000 * 5e-6)
