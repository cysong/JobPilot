"""Loader for YAML-defined Agents."""
from __future__ import annotations

import hashlib
import pickle
import os
from pathlib import Path
from typing import Any

import yaml
from fastapi_cache import FastAPICache
from agents import Agent
from agents.model_settings import ModelSettings

from agent_configs.schemas import SCHEMA_REGISTRY
from app.core.config import settings
from app.core.llm.config import llm_gateway_settings
from app.core.llm.providers import normalize_provider_name

# Ensure OpenAI client finds credentials when using agents SDK
if settings.OPENAI_API_KEY:
    os.environ.setdefault("OPENAI_API_KEY", settings.OPENAI_API_KEY)
if settings.OPENAI_API_BASE:
    os.environ.setdefault("OPENAI_BASE_URL", settings.OPENAI_API_BASE)


class AgentLoader:
    """
    Load Agent definitions from YAML files and cache them in Redis.

    Uses fastapi-cache2 to store Agent instances with automatic invalidation
    based on file modification time.
    """

    def __init__(
        self,
        *,
        config_dir: str | Path | None = None,
    ) -> None:
        self.config_dir = Path(
            config_dir or llm_gateway_settings.AGENT_CONFIG_DIR)

    async def load_agent(self, agent_id: str) -> Agent:
        """
        Load an Agent by ID (YAML filename without extension).

        Hot-reloads when the YAML file's mtime changes.
        Uses Redis cache to store Agent instances for concurrent access.

        Args:
            agent_id: Agent identifier (YAML filename without .yaml)

        Returns:
            Loaded Agent instance

        Raises:
            FileNotFoundError: If agent config file doesn't exist
            ValueError: If config is invalid or output_type is unknown
        """
        config_path = self.config_dir / f"{agent_id}.yaml"
        if not config_path.exists():
            raise FileNotFoundError(f"Agent config not found: {config_path}")

        mtime = config_path.stat().st_mtime

        # Try to get from cache if enabled
        if settings.CACHE_ENABLED:
            cached_agent = await self._get_cached_agent(agent_id, mtime)
            if cached_agent:
                return cached_agent

        # Cache miss or disabled - load from file
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

        # Read model settings from unified nested config.
        # No backward compatibility: top-level temperature/max_tokens/top_p is not supported.
        model_settings_data = config.get("model_settings", {})
        if model_settings_data is None:
            model_settings_data = {}
        if not isinstance(model_settings_data, dict):
            raise ValueError(
                f"Invalid model_settings for agent '{agent_id}': expected object/dict"
            )
        if model_settings_data:
            agent_kwargs["model_settings"] = ModelSettings(**model_settings_data)

        agent = Agent(**agent_kwargs)
        setattr(agent, "agent_id", agent_id)
        setattr(agent, "provider", self._resolve_provider(config))
        setattr(agent, "config_version", config.get("version"))
        setattr(agent, "max_turns", self._resolve_max_turns(config, agent_id))
        setattr(agent, "config_metadata", self._build_config_metadata(config, agent_id))

        # Store in cache if enabled
        if settings.CACHE_ENABLED:
            await self._set_cached_agent(agent_id, mtime, agent)

        return agent

    def _generate_cache_key(self, agent_id: str, mtime: float) -> str:
        """
        Generate cache key that includes mtime for automatic invalidation.

        Args:
            agent_id: Agent identifier
            mtime: File modification time

        Returns:
            Cache key string
        """
        # Include mtime in key so cache auto-invalidates when file changes
        key_data = f"agent:{agent_id}:{mtime}"
        return hashlib.sha256(key_data.encode()).hexdigest()[:32]

    async def _get_cached_agent(self, agent_id: str, mtime: float) -> Agent | None:
        """
        Get cached Agent instance from Redis.

        Args:
            agent_id: Agent identifier
            mtime: Current file modification time

        Returns:
            Cached Agent or None if not found
        """
        cache_key = self._generate_cache_key(agent_id, mtime)

        try:
            backend = FastAPICache.get_backend()
            cached_data = await backend.get(cache_key)

            if cached_data:
                # Deserialize Agent from pickle
                agent = pickle.loads(cached_data)
                return agent

            return None
        except Exception:  # noqa: BLE001
            # Cache error - continue without cache
            return None

    async def _set_cached_agent(
        self, agent_id: str, mtime: float, agent: Agent
    ) -> None:
        """
        Store Agent instance in Redis cache.

        Args:
            agent_id: Agent identifier
            mtime: File modification time
            agent: Agent instance to cache
        """
        cache_key = self._generate_cache_key(agent_id, mtime)

        try:
            backend = FastAPICache.get_backend()
            # Serialize Agent with pickle
            agent_data = pickle.dumps(agent, protocol=pickle.HIGHEST_PROTOCOL)
            # Store with 1 hour TTL
            await backend.set(cache_key, agent_data, expire=3600*24)
        except Exception:  # noqa: BLE001
            # Silently fail on cache write errors
            pass

    def _load_yaml(self, path: Path) -> dict[str, Any]:
        try:
            with path.open("r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except yaml.YAMLError as exc:  # type: ignore[attr-defined]
            raise ValueError(f"Invalid YAML in agent config: {path}") from exc

    def _resolve_schema(self, output_type_name: str | None):
        if not output_type_name:
            raise ValueError(
                "Agent config missing required field 'output_type'")
        schema = SCHEMA_REGISTRY.get(output_type_name)
        if not schema:
            raise ValueError(
                f"Unknown output_type '{output_type_name}' in agent config")
        return schema

    def _resolve_max_turns(self, config: dict[str, Any], agent_id: str) -> int | None:
        """Resolve optional per-agent max_turns override from YAML."""
        max_turns = config.get("max_turns")
        if max_turns is None:
            return None
        if not isinstance(max_turns, int) or max_turns <= 0:
            raise ValueError(
                f"Invalid max_turns for agent '{agent_id}': expected positive integer"
            )
        return max_turns

    def _resolve_provider(self, config: dict[str, Any]) -> str:
        """Resolve optional per-agent provider with backward-compatible default."""
        return normalize_provider_name(config.get("provider"))

    def _build_config_metadata(
        self,
        config: dict[str, Any],
        agent_id: str,
    ) -> dict[str, Any]:
        """Extract a stable subset of YAML config for observability metadata."""
        return {
            "agent_id": agent_id,
            "name": config.get("name", agent_id),
            "version": config.get("version"),
            "provider": self._resolve_provider(config),
            "model": config.get("model"),
            "output_type": config.get("output_type"),
            "max_turns": self._resolve_max_turns(config, agent_id),
            "model_settings": config.get("model_settings") or {},
            "tools": config.get("tools") or [],
            "handoffs": config.get("handoffs") or [],
        }
