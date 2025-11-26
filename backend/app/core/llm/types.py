"""Shared types for the LLM gateway."""
from __future__ import annotations

from typing import Any, TypedDict


class GatewayContext(TypedDict, total=False):
    """Context passed into AgentGateway for logging and outbox."""

    db: Any
    workflow_id: str
    task_id: str
    user_id: str | int
    operation: str
