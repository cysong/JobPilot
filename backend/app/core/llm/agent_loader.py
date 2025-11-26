"""Loader for YAML-defined Agents."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from openai_agents import Agent

from agents.schemas import SCHEMA_REGISTRY
from app.core.llm.config import llm_gateway_settings


@dataclass
class CachedAgent:
    """Cached agent with metadata to support hot reloads."""

    agent: Agent
    version: int | str | None
    mtime: float


class AgentLoader:
    """Load Agent definitions from YAML files and cache them."""

    def __init__(
        self,
        *,
        config_dir: str | Path | None = None,
    ) -> None:
        self.config_dir = Path(config_dir or llm_gateway_settings.AGENT_CONFIG_DIR)
        self._cache: dict[str, CachedAgent] = {}

    def load_agent(self, agent_id: str) -> Agent:
        """
        Load an Agent by ID (YAML filename without extension).

        Hot-reloads when the YAML file's mtime changes.
        """
        config_path = self.config_dir / f"{agent_id}.yaml"
        if not config_path.exists():
            raise FileNotFoundError(f"Agent config not found: {config_path}")

        mtime = config_path.stat().st_mtime
        cached = self._cache.get(agent_id)
        if cached and cached.mtime == mtime:
            return cached.agent

        config = self._load_yaml(config_path)
        output_type_name = config.get("output_type")
        schema = self._resolve_schema(output_type_name)

        agent_kwargs: dict[str, Any] = {
            "name": config.get("name", agent_id),
            "model": config["model"],
            "instructions": config["instructions"],
            "output_type": schema,
            "tools": config.get("tools") or [],
            "handoffs": config.get("handoffs") or [],
        }

        for optional_key in ("temperature", "max_tokens", "top_p"):
            if optional_key in config:
                agent_kwargs[optional_key] = config[optional_key]

        agent = Agent(**agent_kwargs)
        setattr(agent, "agent_id", agent_id)
        setattr(agent, "config_version", config.get("version"))

        self._cache[agent_id] = CachedAgent(
            agent=agent,
            version=config.get("version"),
            mtime=mtime,
        )
        return agent

    def _load_yaml(self, path: Path) -> dict[str, Any]:
        try:
            with path.open("r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except yaml.YAMLError as exc:  # type: ignore[attr-defined]
            raise ValueError(f"Invalid YAML in agent config: {path}") from exc

    def _resolve_schema(self, output_type_name: str | None):
        if not output_type_name:
            raise ValueError("Agent config missing required field 'output_type'")
        schema = SCHEMA_REGISTRY.get(output_type_name)
        if not schema:
            raise ValueError(f"Unknown output_type '{output_type_name}' in agent config")
        return schema
