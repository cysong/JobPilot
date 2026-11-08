"""Every agent YAML must load, and OpenRouter agents may only send parameters their model accepts.

OpenRouter requests carry provider.require_parameters=true, so an unsupported
parameter (e.g. `verbosity` on GLM, `temperature` on GPT-6.1 Terra) makes the
request fail to route instead of being silently ignored.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from app.core.config import settings
from app.core.llm.agent_loader import AgentLoader

CONFIG_DIR = Path(__file__).resolve().parents[2] / "agent_configs" / "config"
AGENT_IDS = sorted(p.stem for p in CONFIG_DIR.glob("*.yaml"))

# Snapshot of OpenRouter `supported_parameters` (catalog, 2026-11-08) mapped to
# the ModelSettings keys that produce them.
OPENROUTER_ALLOWED_SETTINGS = {
    "openai/gpt-6.1-terra": {"max_tokens", "reasoning", "verbosity", "extra_args", "tool_choice"},
    "openai/gpt-6.1-sol": {"max_tokens", "reasoning", "verbosity", "extra_args", "tool_choice"},
    "z-ai/glm-5.3-flash": {"max_tokens", "reasoning", "temperature", "top_p", "extra_args", "tool_choice"},
}
OPENROUTER_ALLOWED_EXTRA_ARGS = {"seed"}


def _config(agent_id: str) -> dict:
    return yaml.safe_load((CONFIG_DIR / f"{agent_id}.yaml").read_text())


@pytest.mark.asyncio
@pytest.mark.parametrize("agent_id", AGENT_IDS)
async def test_every_agent_config_loads(agent_id, monkeypatch):
    monkeypatch.setattr(settings, "CACHE_ENABLED", False)
    agent = await AgentLoader(config_dir=CONFIG_DIR).load_agent(agent_id)
    assert agent.model
    assert getattr(agent, "provider") in {"openai", "minimax", "openrouter"}


@pytest.mark.parametrize("agent_id", [a for a in AGENT_IDS if _config(a).get("provider") == "openrouter"])
def test_openrouter_agents_only_send_supported_parameters(agent_id):
    config = _config(agent_id)
    model = config["model"]
    assert model in OPENROUTER_ALLOWED_SETTINGS, f"add {model} to the allowed-settings snapshot"
    settings_keys = set((config.get("model_settings") or {}).keys())
    unsupported = settings_keys - OPENROUTER_ALLOWED_SETTINGS[model]
    assert not unsupported, f"{agent_id}: {model} does not accept {sorted(unsupported)}"
    extra_args = set(((config.get("model_settings") or {}).get("extra_args") or {}).keys())
    assert extra_args <= OPENROUTER_ALLOWED_EXTRA_ARGS, f"{agent_id}: unexpected extra_args {extra_args}"


def test_switched_agents_use_the_chosen_models():
    strong = {"cover_letter_writer", "cover_letter_polisher", "resume_tailor", "resume_analyzer",
              "reviewer", "match_judge"}
    light = {"job_analyzer", "universal_translator", "title_classifier", "job_family_reader"}
    for agent_id in strong:
        assert _config(agent_id)["model"] == "openai/gpt-6.1-terra", agent_id
    for agent_id in light:
        assert _config(agent_id)["model"] == "z-ai/glm-5.3-flash", agent_id
