"""Shared types for the LLM gateway."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TypedDict


class GatewayContext(TypedDict, total=False):
    """Context passed into AgentGateway for logging and outbox."""

    db: Any
    workflow_id: str
    task_id: str
    user_id: str | int
    operation: str
    # Written back by the gateway after the call is recorded.
    ai_call_id: str
    # Written back by the gateway after a successful call:
    # {model, provider, input_tokens, output_tokens, estimated_cost}
    usage: dict[str, Any]


@dataclass(frozen=True)
class ModelOverride:
    """Per-call override of the provider/model/settings defined in an agent YAML.

    Used to run the same prompt against different models (e.g. evaluation runs)
    without duplicating agent configs. ``None`` fields keep the YAML value;
    ``model_settings`` is merged over the YAML model_settings.
    """

    provider: str | None = None
    model: str | None = None
    model_settings: dict[str, Any] = field(default_factory=dict)
