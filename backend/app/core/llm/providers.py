"""Provider-aware runtime helpers for the LLM gateway."""
from __future__ import annotations

import asyncio
import contextvars
import json
from dataclasses import dataclass, field
from typing import Any, Literal

import httpx
from agents.models.multi_provider import MultiProvider
from openai import AsyncOpenAI, DefaultAsyncHttpxClient

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


# OpenRouter routes one model to many upstream hosts that differ in quantization and
# output quality. The gateway puts a dict here before each call; the HTTP hook below
# fills it from the response so failures can be traced to the host that served them.
# A mutable dict is shared rather than set, because the Agents SDK runs the request in
# a copied context (asyncio.wait_for creates a new task).
upstream_capture: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar(
    "llm_upstream_capture", default=None
)


async def _capture_openrouter_upstream(response: httpx.Response) -> None:
    capture = upstream_capture.get()
    if capture is None or not response.request.url.path.endswith("/chat/completions"):
        return
    if "text/event-stream" in response.headers.get("content-type", ""):
        return  # reading a stream here would buffer it; nothing in the app streams today
    try:
        await response.aread()
        payload = json.loads(response.content)
    except Exception:  # noqa: BLE001 - observability must never break the call
        return
    if not isinstance(payload, dict):
        return
    usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
    capture.update({
        "upstream": payload.get("provider"),
        "generation_id": payload.get("id"),
        "cost": usage.get("cost"),
    })


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
            http_client=_openrouter_http_client(),
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


class _OpenRouterHttpClient(DefaultAsyncHttpxClient):
    """httpx client with the upstream capture hook.

    A new client per runtime, like the AsyncOpenAI default: worker threads each run
    their own event loop, so a pooled client must not be shared between calls. Like the
    SDK's own default wrapper, it closes itself when garbage-collected.
    """

    def __init__(self) -> None:
        super().__init__(event_hooks={"response": [_capture_openrouter_upstream]})

    def __del__(self) -> None:
        if self.is_closed:
            return
        try:
            asyncio.get_running_loop().create_task(self.aclose())
        except Exception:  # noqa: BLE001 - no running loop: the pool is dropped with the object
            pass


def _openrouter_http_client() -> httpx.AsyncClient:
    return _OpenRouterHttpClient()


def _build_client(
    *, api_key: str, base_url: str, provider: ProviderName, http_client: httpx.AsyncClient | None = None
) -> AsyncOpenAI:
    """Construct an AsyncOpenAI client for an OpenAI-compatible provider."""
    if not api_key:
        raise ValueError(f"Missing API key for provider '{provider}'")
    return AsyncOpenAI(api_key=api_key, base_url=base_url, http_client=http_client)
