"""Configuration for the LLM gateway components."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMGatewaySettings(BaseSettings):
    """LLM Gateway configuration loaded from environment variables."""

    # Agent config directory
    AGENT_CONFIG_DIR: str = "agent_configs/config"

    # Gateway safeguards
    AGENT_DEFAULT_TIMEOUT: int = 180
    AGENT_MAX_TURNS: int = 6

    # Cache settings
    ENABLE_JD_CACHE: bool = True
    ENABLE_RESUME_CACHE: bool = True
    CACHE_VERSION: int = 1

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="LLM_",
        case_sensitive=True,
        extra="ignore",
    )


# Global settings instance
llm_gateway_settings = LLMGatewaySettings()


# Model pricing (per million tokens)
MODEL_PRICING: dict[str, dict[str, float]] = {
    "deepseek-chat": {
        "input": 0.14 / 1_000_000,   # $0.14 per 1M input tokens
        "output": 0.28 / 1_000_000,  # $0.28 per 1M output tokens
    },
    "MiniMax-M2.5": {
        "input": 0.30 / 1_000_000,
        "output": 1.20 / 1_000_000,
    },
    "MiniMax-M2.5-highspeed": {
        "input": 0.30 / 1_000_000,
        "output": 2.40 / 1_000_000,
    },
    "MiniMax-M2.1": {
        "input": 0.30 / 1_000_000,
        "output": 1.20 / 1_000_000,
    },
    "MiniMax-M2.1-highspeed": {
        "input": 0.30 / 1_000_000,
        "output": 2.40 / 1_000_000,
    },
    "gpt-5": {
        "input": 1.25 / 1_000_000,
        "output": 10.0 / 1_000_000,
    },
    "gpt-5-mini": {
        "input": 0.25 / 1_000_000,
        "output": 2.0 / 1_000_000,
    },
    "gpt-4o": {
        "input": 2.50 / 1_000_000,
        "output": 10.0 / 1_000_000,
    },
    "gpt-4o-mini": {
        "input": 0.15 / 1_000_000,
        "output": 0.60 / 1_000_000,
    },
}
