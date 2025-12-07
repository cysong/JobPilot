"""Repository for AICall entities."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.workflow import AICall
from app.shared.enums import AICallStatus


class AICallRepository:
    """Data access helpers for AI calls."""

    @staticmethod
    async def create(
        db: AsyncSession,
        *,
        workflow_id: str,
        task_id: str,
        user_id: int,
        agent_id: str,
        agent_version: Optional[str],
        model: str,
        status: AICallStatus,
        latency_ms: int,
        input_tokens: Optional[int] = None,
        output_tokens: Optional[int] = None,
        total_tokens: Optional[int] = None,
        requests: Optional[int] = None,
        estimated_cost: Optional[float] = None,
        error_message: Optional[str] = None,
        meta: Optional[dict] = None,
    ) -> AICall:
        """
        Create a new AI call record.

        Args:
            db: Database session
            workflow_id: Associated workflow ID
            task_id: Associated task ID
            user_id: User who initiated the call
            agent_id: Agent identifier
            agent_version: Agent configuration version
            model: Model name (e.g., "gpt-4o")
            status: Call status (SUCCESS, ERROR, etc.)
            latency_ms: Call latency in milliseconds
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            total_tokens: Total tokens used
            requests: Number of API requests made
            estimated_cost: Estimated cost in USD
            error_message: Error message if failed
            meta: Additional metadata

        Returns:
            Created AICall instance
        """
        ai_call = AICall(
            workflow_id=workflow_id,
            task_id=task_id,
            user_id=user_id,
            model=model,
            agent_id=agent_id,
            agent_version=agent_version,
            status=status,
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            requests=requests,
            estimated_cost=estimated_cost,
            error_message=error_message,
            meta=meta or {},
        )
        db.add(ai_call)
        await db.flush()
        return ai_call

    @staticmethod
    async def get_by_id(db: AsyncSession, ai_call_id: int) -> AICall | None:
        """Get AI call by ID."""
        query = select(AICall).where(AICall.id == ai_call_id)
        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_workflow_id(
        db: AsyncSession, workflow_id: str
    ) -> list[AICall]:
        """Get all AI calls for a workflow."""
        query = select(AICall).where(AICall.workflow_id == workflow_id)
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get_by_task_id(db: AsyncSession, task_id: str) -> list[AICall]:
        """Get all AI calls for a task."""
        query = select(AICall).where(AICall.task_id == task_id)
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get_by_user_id(
        db: AsyncSession, user_id: int, limit: int = 100
    ) -> list[AICall]:
        """Get recent AI calls for a user."""
        query = (
            select(AICall)
            .where(AICall.user_id == user_id)
            .order_by(AICall.created_at.desc())
            .limit(limit)
        )
        result = await db.execute(query)
        return list(result.scalars().all())
