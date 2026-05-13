"""Unified gateway for executing Agents with logging."""
from __future__ import annotations

import asyncio
import time
from typing import Any, Optional

import structlog
from agents import Agent, Runner
from agents import Usage
from agents.run_config import RunConfig

from app.core.database import async_session_factory
from app.core.llm.agent_loader import AgentLoader
from app.core.llm.config import MODEL_PRICING, llm_gateway_settings
from app.core.llm.providers import build_provider_runtime
from app.core.llm.types import GatewayContext
from app.core.metrics import (
    llm_call_duration_seconds,
    llm_call_total,
    llm_tokens_total,
)
from app.modules.workflow import AICallRepository
from app.shared.enums import AICallStatus

logger = structlog.get_logger()


class AgentGateway:
    """
    Singleton gateway for executing Agents with observability.

    Usage:
        gateway = AgentGateway.get()
        result, usage = await gateway.call("agent_id", input_data)
    """

    _instance: Optional["AgentGateway"] = None

    def __init__(self, loader: Optional[AgentLoader] = None) -> None:
        """Internal constructor - use get() to obtain singleton instance."""
        self.loader = loader or AgentLoader()

    @classmethod
    def get(cls) -> "AgentGateway":
        """Get singleton instance of AgentGateway."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def call(
        self,
        agent_id: str,
        input_data: str,
        context: GatewayContext | None = None,
    ) -> Any:
        """
        Execute an Agent and return its output.

        Args:
            agent_id: Agent identifier (YAML filename)
            input_data: Input string for the agent (plain text or YAML-formatted)
            context: Additional metadata for logging

        Returns:
            Agent output (final_output)
        """
        context = context or {}
        start_time = time.time()

        agent = await self.loader.load_agent(agent_id)
        self._log_start(agent_id, agent, context)

        try:
            result, usage = await self._execute_agent(agent, input_data)
            latency_ms = int((time.time() - start_time) * 1000)

            self._log_success(agent_id, agent, usage, latency_ms, context)
            await self._record_ai_call(
                agent_id=agent_id,
                agent=agent,
                status="success",
                latency_ms=latency_ms,
                usage=usage,
                context=context,
            )

            return result

        except Exception as exc:  # noqa: BLE001
            error_type = self._classify_error(exc)
            latency_ms = int((time.time() - start_time) * 1000)

            self._log_error(agent_id, agent, error_type,
                            exc, latency_ms, context)
            await self._record_ai_call(
                agent_id=agent_id,
                agent=agent,
                status=error_type,
                latency_ms=latency_ms,
                error_message=str(exc),
                context=context,
            )
            raise

    async def _execute_agent(
        self, agent: Agent, input_data: str
    ) -> tuple[Any, Optional[Usage]]:
        """
        Execute Agent and extract result and usage.

        Args:
            agent: Agent instance
            input_data: Input string (plain text or YAML-formatted)

        Returns:
            Tuple of (final_output, usage)
        """
        provider_runtime = build_provider_runtime(getattr(agent, "provider", None))
        run_kwargs: dict[str, Any] = {
            "run_config": RunConfig(
                reasoning_item_id_policy="omit",
                model_provider=provider_runtime.model_provider,
                tracing_disabled=provider_runtime.tracing_disabled,
            ),
        }
        max_turns = getattr(agent, "max_turns", None)
        if not isinstance(max_turns, int) or max_turns <= 0:
            max_turns = llm_gateway_settings.AGENT_MAX_TURNS
        if max_turns > 0:
            run_kwargs["max_turns"] = max_turns

        call_coro = Runner.run(agent, input_data, **run_kwargs)
        if llm_gateway_settings.AGENT_DEFAULT_TIMEOUT > 0:
            timeout_seconds = llm_gateway_settings.AGENT_DEFAULT_TIMEOUT
            try:
                result = await asyncio.wait_for(
                    call_coro,
                    timeout=timeout_seconds,
                )
            except asyncio.TimeoutError as exc:
                raise TimeoutError(
                    f"Agent call timed out after {timeout_seconds}s"
                ) from exc
        else:
            result = await call_coro
        usage = getattr(
            getattr(result, "context_wrapper", None), "usage", None)
        final_output = getattr(result, "final_output", None)
        return final_output, usage

    def _log_start(
        self, agent_id: str, agent: Agent, context: GatewayContext
    ) -> None:
        """Log agent call started."""
        logger.info(
            "agent_call_started",
            agent_id=agent_id,
            task_id=context.get("task_id"),
            provider=getattr(agent, "provider", None),
            model=getattr(agent, "model", None),
            operation=context.get("operation"),
        )

    def _log_success(
        self,
        agent_id: str,
        agent: Agent,
        usage: Optional[Usage],
        latency_ms: int,
        context: GatewayContext,
    ) -> None:
        """Log successful agent call with metrics."""
        estimated_cost = self._calculate_cost(
            getattr(agent, "model", ""),
            getattr(usage, "input_tokens", 0) or 0,
            getattr(usage, "output_tokens", 0) or 0,
        )

        provider = getattr(agent, "provider", None) or "unknown"
        model = getattr(agent, "model", None) or "unknown"
        input_tokens = getattr(usage, "input_tokens", 0) or 0
        output_tokens = getattr(usage, "output_tokens", 0) or 0

        llm_call_total.labels(
            agent_id=agent_id, provider=provider, model=model, outcome="ok"
        ).inc()
        llm_call_duration_seconds.labels(
            agent_id=agent_id, provider=provider, model=model
        ).observe(latency_ms / 1000.0)
        # Always touch both kinds so the label combinations are discoverable in
        # PromQL even for tool-only calls that produce zero tokens.
        llm_tokens_total.labels(
            agent_id=agent_id, provider=provider, model=model, kind="input"
        ).inc(input_tokens)
        llm_tokens_total.labels(
            agent_id=agent_id, provider=provider, model=model, kind="output"
        ).inc(output_tokens)

        logger.info(
            "agent_call_completed",
            agent_id=agent_id,
            task_id=context.get("task_id"),
            provider=getattr(agent, "provider", None),
            model=getattr(agent, "model", None),
            status="success",
            latency_ms=latency_ms,
            input_tokens=getattr(usage, "input_tokens", None),
            output_tokens=getattr(usage, "output_tokens", None),
            total_tokens=getattr(usage, "total_tokens", None),
            requests=getattr(usage, "requests", None),
            estimated_cost=estimated_cost,
            operation=context.get("operation"),
        )

    def _log_error(
        self,
        agent_id: str,
        agent: Agent,
        error_type: str,
        error: Exception,
        latency_ms: int,
        context: GatewayContext,
    ) -> None:
        """Log failed agent call."""
        provider = getattr(agent, "provider", None) or "unknown"
        model = getattr(agent, "model", None) or "unknown"

        llm_call_total.labels(
            agent_id=agent_id, provider=provider, model=model, outcome=error_type
        ).inc()
        llm_call_duration_seconds.labels(
            agent_id=agent_id, provider=provider, model=model
        ).observe(latency_ms / 1000.0)

        error_details = self._extract_error_details(error)
        logger.error(
            "agent_call_failed",
            agent_id=agent_id,
            task_id=context.get("task_id"),
            provider=getattr(agent, "provider", None),
            model=getattr(agent, "model", None),
            status=error_type,
            error=str(error),
            error_class=error_details["error_class"],
            error_message=error_details["error_message"],
            error_args=error_details["error_args"],
            cause_class=error_details["cause_class"],
            cause_message=error_details["cause_message"],
            context_class=error_details["context_class"],
            context_message=error_details["context_message"],
            turn_limit_hit=error_details["turn_limit_hit"],
            schema_related=error_details["schema_related"],
            max_turns_setting=llm_gateway_settings.AGENT_MAX_TURNS,
            latency_ms=latency_ms,
            operation=context.get("operation"),
            exc_info=True,
        )

    async def _record_ai_call(
        self,
        *,
        agent_id: str,
        agent: Agent,
        status: str,
        latency_ms: int,
        usage: Optional[Usage] = None,
        error_message: Optional[str] = None,
        context: GatewayContext,
    ) -> None:
        """
        Record AI call to database (success or failure).

        Creates an ai_call record for tracking and analytics.
        """
        task_id = context.get("task_id")
        user_id = context.get("user_id")

        # Skip recording if missing required task context
        if not task_id:
            return

        # Map status string to AICallStatus enum
        status_map = {
            "success": AICallStatus.SUCCESS,
            "error": AICallStatus.FAILED,
            "ratelimit": AICallStatus.FAILED,
            "timeout": AICallStatus.FAILED,
            "auth_error": AICallStatus.FAILED,
            "max_turns": AICallStatus.FAILED,
        }
        ai_call_status = status_map.get(status, AICallStatus.FAILED)

        # Calculate estimated cost
        estimated_cost = None
        if usage and ai_call_status == AICallStatus.SUCCESS:
            estimated_cost = self._calculate_cost(
                getattr(agent, "model", ""),
                getattr(usage, "input_tokens", 0) or 0,
                getattr(usage, "output_tokens", 0) or 0,
            )

        # Convert agent version to string (config_version may be int from YAML)
        version = getattr(agent, "config_version", None)
        agent_version_str = str(version) if version is not None else ""
        model_provider = getattr(agent, "provider", None)
        if not model_provider:
            raise ValueError(
                f"Agent '{agent_id}' is missing required provider for AI call tracking"
            )

        try:
            # Persist usage records in an independent transaction so task rollbacks
            # don't erase observability data on failures/retries.
            async with async_session_factory() as db:
                agent_config_metadata = getattr(agent, "config_metadata", {}) or {}
                await AICallRepository.create(
                    db,
                    task_id=task_id,
                    user_id=user_id,
                    agent_id=agent_id,
                    agent_version=agent_version_str,
                    model=getattr(agent, "model", ""),
                    model_provider=model_provider,
                    status=ai_call_status,
                    latency_ms=latency_ms,
                    input_tokens=getattr(usage, "input_tokens",
                                         None) if usage else None,
                    output_tokens=getattr(usage, "output_tokens",
                                          None) if usage else None,
                    total_tokens=getattr(usage, "total_tokens",
                                         None) if usage else None,
                    requests=getattr(usage, "requests", None) if usage else None,
                    estimated_cost=estimated_cost,
                    error_message=error_message,
                    metadata={
                        "operation": context.get("operation"),
                        "agent_id": agent_id,
                        "provider": model_provider,
                        "agent_version": agent_version_str,
                        "agent_config": agent_config_metadata,
                    },
                )
                await db.commit()
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "ai_call_record_failed",
                task_id=task_id,
                agent_id=agent_id,
                error=str(exc),
            )

    @staticmethod
    def _classify_error(error: Exception) -> str:
        """Classify error type for metrics."""
        error_name = type(error).__name__
        error_message = str(error).lower()

        if "RateLimit" in error_name:
            return "ratelimit"
        if "Timeout" in error_name:
            return "timeout"
        if "Authentication" in error_name or "Auth" in error_name:
            return "auth_error"
        if "max turns exceeded" in error_message or "max_turns" in error_message:
            return "max_turns"
        return "error"

    @staticmethod
    def _extract_error_details(error: Exception) -> dict[str, Any]:
        """Extract structured error details to simplify root-cause analysis."""
        cause = error.__cause__
        context = error.__context__
        error_message = str(error)
        error_message_lower = error_message.lower()
        cause_message = str(cause) if cause else ""
        context_message = str(context) if context else ""
        joined = f"{error_message_lower} {cause_message.lower()} {context_message.lower()}"
        schema_keywords = ("schema", "validation", "pydantic", "json", "output_type")

        return {
            "error_class": type(error).__name__,
            "error_message": error_message,
            "error_args": [str(arg) for arg in error.args[:5]],
            "cause_class": type(cause).__name__ if cause else None,
            "cause_message": cause_message or None,
            "context_class": type(context).__name__ if context else None,
            "context_message": context_message or None,
            "turn_limit_hit": "max turns exceeded" in joined or "max_turns" in joined,
            "schema_related": any(keyword in joined for keyword in schema_keywords),
        }

    @staticmethod
    def _calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
        """Calculate estimated cost based on model pricing."""
        pricing = MODEL_PRICING.get(model, {"input": 0, "output": 0})
        return round(
            (input_tokens or 0) * pricing["input"]
            + (output_tokens or 0) * pricing["output"],
            6,
        )
