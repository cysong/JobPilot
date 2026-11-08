"""Provider-aware runtime helpers for the LLM gateway."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from agents.models.multi_provider import MultiProvider
from openai import AsyncOpenAI

from app.core.config import settings

ProviderName = Literal["openai", "minimax", "openrouter"]
ProviderApiMode = Literal["responses", "chat_completions"]

SUPPORTED_PROVIDERS: frozenset[str] = frozenset({"openai", "minimax", "openrouter"})

# OpenRouter routing preferences sent with every request:
# - require_parameters: only route to upstreams that honour every request
#   parameter (structured output in particular), instead of silently dropping it.
# - data_collection=deny: resumes contain personal data; exclude upstreams that
#   may store or train on prompts.
OPENROUTER_PROVIDER_PREFERENCES: dict[str, Any] = {
    "require_parameters": True,
    "data_collection": "deny",
}


@dataclass(frozen=True)
class ProviderRuntime:
    """Resolved runtime configuration for an LLM provider."""

    provider: ProviderName
    api_mode: ProviderApiMode
    tracing_disabled: bool
    model_provider: MultiProvider
    # Merged into ModelSettings.extra_body for every call on this provider.
    default_extra_body: dict[str, Any] = field(default_factory=dict)


def normalize_provider_name(provider_name: str | None) -> ProviderName:
    """Normalize and validate a provider identifier."""
    normalized = (provider_name or settings.DEFAULT_LLM_PROVIDER or "openai").strip().lower()
    if normalized not in SUPPORTED_PROVIDERS:
        raise ValueError(f"Unsupported LLM provider: {provider_name}")
    return normalized  # type: ignore[return-value]


def build_provider_runtime(provider_name: str | None = None) -> ProviderRuntime:
    """Build provider-specific runtime wiring for the Agents SDK."""
    resolved_provider = normalize_provider_name(provider_name)

    if resolved_provider == "openrouter":
        client = _build_client(
            api_key=settings.OPENROUTER_API_KEY,
            base_url=settings.OPENROUTER_API_BASE,
            provider="openrouter",
        )
        return ProviderRuntime(
            provider="openrouter",
            api_mode="chat_completions",
            tracing_disabled=True,
            # OpenRouter model ids are namespaced ("openai/gpt-6.1-terra",
            # "z-ai/glm-5.3-flash"); pass them through verbatim instead of
            # letting MultiProvider treat the prefix as a provider name.
            model_provider=MultiProvider(
                openai_client=client,
                openai_use_responses=False,
                openai_prefix_mode="model_id",
                unknown_prefix_mode="model_id",
            ),
            default_extra_body={"provider": dict(OPENROUTER_PROVIDER_PREFERENCES)},
        )

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
