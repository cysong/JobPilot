"""Provider-aware runtime helpers for the LLM gateway."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from agents.models.multi_provider import MultiProvider
from openai import AsyncOpenAI

from app.core.config import settings

ProviderName = Literal["openai", "minimax"]
ProviderApiMode = Literal["responses", "chat_completions"]


@dataclass(frozen=True)
class ProviderRuntime:
    """Resolved runtime configuration for an LLM provider."""

    provider: ProviderName
    api_mode: ProviderApiMode
    tracing_disabled: bool
    model_provider: MultiProvider


def normalize_provider_name(provider_name: str | None) -> ProviderName:
    """Normalize and validate a provider identifier."""
    normalized = (provider_name or settings.DEFAULT_LLM_PROVIDER or "openai").strip().lower()
    if normalized not in {"openai", "minimax"}:
        raise ValueError(f"Unsupported LLM provider: {provider_name}")
    return normalized  # type: ignore[return-value]


def build_provider_runtime(provider_name: str | None = None) -> ProviderRuntime:
    """Build provider-specific runtime wiring for the Agents SDK."""
    resolved_provider = normalize_provider_name(provider_name)

    if resolved_provider == "minimax":
        client = _build_client(
            api_key=settings.MINIMAX_API_KEY,
            base_url=settings.MINIMAX_API_BASE,
            provider="minimax",
        )
        return ProviderRuntime(
            provider="minimax",
            api_mode="chat_completions",
            tracing_disabled=not settings.MINIMAX_TRACING_ENABLED,
            model_provider=MultiProvider(
                openai_client=client,
                openai_use_responses=False,
            ),
        )

    client = _build_client(
        api_key=settings.OPENAI_API_KEY,
        base_url=settings.OPENAI_API_BASE,
        provider="openai",
    )
    return ProviderRuntime(
        provider="openai",
        api_mode="responses",
        tracing_disabled=not settings.OPENAI_TRACING_ENABLED,
        model_provider=MultiProvider(
            openai_client=client,
            openai_use_responses=True,
        ),
    )


def _build_client(*, api_key: str, base_url: str, provider: ProviderName) -> AsyncOpenAI:
    """Construct an AsyncOpenAI client for an OpenAI-compatible provider."""
    if not api_key:
        raise ValueError(f"Missing API key for provider '{provider}'")
    return AsyncOpenAI(api_key=api_key, base_url=base_url)
