"""Unified gateway for executing Agents with logging and outbox events."""
from __future__ import annotations

import time
from typing import Any, Optional

import structlog
from openai_agents import Agent, Runner
from openai_agents.types import Usage

from app.core.llm.agent_loader import AgentLoader
from app.core.llm.config import MODEL_PRICING
from app.core.llm.types import GatewayContext
from app.modules.applications.repositories.outbox_repo import OutboxRepository

logger = structlog.get_logger()


class AgentGateway:
    """Central entrypoint for running Agents with observability hooks."""

    def __init__(self, loader: Optional[AgentLoader] = None) -> None:
        self.loader = loader or AgentLoader()

    async def call(
        self,
        agent_id: str,
        input_data: Any,
        context: GatewayContext | None = None,
    ) -> tuple[Any, Optional[Usage]]:
        """
        Execute an Agent and return its output plus usage.

        Args:
            agent_id: Agent identifier (YAML filename)
            input_data: Input prompt or payload
            context: Additional metadata for logging/outbox
        """
        context = context or {}
        start_time = time.time()

        agent = self.loader.load_agent(agent_id)

        logger.info(
            "agent_call_started",
            agent_id=agent_id,
            model=getattr(agent, "model", None),
            workflow_id=context.get("workflow_id"),
            operation=context.get("operation"),
        )

        try:
            result = await Runner.run(agent, input_data)
            usage = getattr(getattr(result, "context_wrapper", None), "usage", None)

            latency_ms = int((time.time() - start_time) * 1000)
            estimated_cost = self._calculate_cost(
                getattr(agent, "model", ""),
                getattr(usage, "input_tokens", 0) or 0,
                getattr(usage, "output_tokens", 0) or 0,
            )

            logger.info(
                "agent_call_completed",
                agent_id=agent_id,
                model=getattr(agent, "model", None),
                status="success",
                latency_ms=latency_ms,
                input_tokens=getattr(usage, "input_tokens", None),
                output_tokens=getattr(usage, "output_tokens", None),
                total_tokens=getattr(usage, "total_tokens", None),
                requests=getattr(usage, "requests", None),
                estimated_cost=estimated_cost,
                workflow_id=context.get("workflow_id"),
                operation=context.get("operation"),
            )

            await self._enqueue_outbox(
                context=context,
                agent=agent,
                status="success",
                usage=usage,
                latency_ms=latency_ms,
                estimated_cost=estimated_cost,
            )

            return getattr(result, "final_output", None), usage

        except Exception as exc:  # noqa: BLE001
            error_type = self._classify_error(exc)
            latency_ms = int((time.time() - start_time) * 1000)

            logger.error(
                "agent_call_failed",
                agent_id=agent_id,
                model=getattr(agent, "model", None),
                status=error_type,
                error=str(exc),
                latency_ms=latency_ms,
                workflow_id=context.get("workflow_id"),
            )

            await self._enqueue_outbox(
                context=context,
                agent=agent,
                status=error_type,
                latency_ms=latency_ms,
                error_message=str(exc),
            )
            raise

    @staticmethod
    def _classify_error(error: Exception) -> str:
        """Classify error type for metrics."""
        error_name = type(error).__name__

        if "RateLimit" in error_name:
            return "ratelimit"
        if "Timeout" in error_name:
            return "timeout"
        if "Authentication" in error_name or "Auth" in error_name:
            return "auth_error"
        return "error"

    @staticmethod
    def _calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
        """Calculate estimated cost based on model pricing."""
        pricing = MODEL_PRICING.get(model, {"input": 0, "output": 0})
        return round(
            (input_tokens or 0) * pricing["input"]
            + (output_tokens or 0) * pricing["output"],
            6,
        )

    async def _enqueue_outbox(
        self,
        *,
        context: GatewayContext,
        agent: Agent,
        status: str,
        latency_ms: int,
        estimated_cost: float | None = None,
        usage: Usage | None = None,
        error_message: str | None = None,
    ) -> None:
        """Write ai_call_completed event into Outbox when db/workflow info is provided."""
        db = context.get("db")
        workflow_id = context.get("workflow_id")

        if not db or not workflow_id:
            return

        await OutboxRepository.enqueue_event(
            db=db,
            event_type="ai_call_completed",
            aggregate_type="workflow",
            aggregate_id=str(workflow_id),
            payload={
                "agent_id": getattr(agent, "agent_id", None),
                "agent_version": getattr(agent, "config_version", None),
                "model": getattr(agent, "model", None),
                "status": status,
                "input_tokens": getattr(usage, "input_tokens", None),
                "output_tokens": getattr(usage, "output_tokens", None),
                "total_tokens": getattr(usage, "total_tokens", None),
                "requests": getattr(usage, "requests", None),
                "estimated_cost": estimated_cost,
                "latency_ms": latency_ms,
                "operation": context.get("operation"),
                "user_id": context.get("user_id"),
                "task_id": context.get("task_id"),
                "error_message": error_message,
            },
            meta={"user_id": context.get("user_id")},
        )
