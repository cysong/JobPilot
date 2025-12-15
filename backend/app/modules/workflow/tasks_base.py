"""Celery task base classes for async execution and DB-backed tracking."""
from __future__ import annotations

import asyncio
import time
from typing import Any

from celery import Task
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory
from app.modules.workflow.repositories import TaskRepository


class AsyncBaseTask(Task):
    """Async-aware Celery task that injects `self.db` session."""

    abstract = True
    auto_commit = False
    _db_session: AsyncSession | None = None

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        if asyncio.iscoroutinefunction(self.run):
            return self._run_async_task(*args, **kwargs)
        return super().__call__(*args, **kwargs)

    def _run_async_task(self, *args: Any, **kwargs: Any) -> Any:
        async def _execute():
            async with async_session_factory() as session:
                self._db_session = session
                try:
                    result = await self.run(*args, **kwargs)
                    if self.auto_commit:
                        await session.commit()
                    return result
                except Exception:
                    await session.rollback()
                    raise
                finally:
                    self._db_session = None

        return asyncio.run(_execute())

    @property
    def db(self) -> AsyncSession:
        if not self._db_session:
            raise RuntimeError("Database session is not available")
        return self._db_session


class DBTrackingTask(AsyncBaseTask):
    """Async task base with automatic task_executions state tracking."""

    abstract = True
    auto_commit = False

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        self._task_id = kwargs.get("task_id")
        self._workflow_id = kwargs.get("workflow_id")
        if not self._task_id:
            raise ValueError("DBTrackingTask requires task_id")
        self._start_time = time.perf_counter()
        return super().__call__(*args, **kwargs)

    def on_retry(self, exc: Exception, task_id: str, args: Any, kwargs: Any, einfo: Any) -> None:
        """Update retry count when Celery schedules a retry."""
        retry_count = getattr(self.request, "retries", None)
        asyncio.run(self._update_retry_status(task_id, retry_count))
        return super().on_retry(exc, task_id, args, kwargs, einfo)

    def _run_async_task(self, *args: Any, **kwargs: Any) -> Any:
        async def _execute():
            async with async_session_factory() as session:
                self._db_session = session
                task = await TaskRepository.get_by_id(session, self._task_id)
                if task:
                    await TaskRepository.mark_running(
                        session,
                        task,
                        celery_task_id=getattr(self.request, "id", None),
                        worker_id=getattr(self.request, "hostname", None),
                        retry_count=getattr(self.request, "retries", None),
                    )
                    await session.commit()

                try:
                    result = await self.run(*args, **kwargs)
                    if task:
                        elapsed_ms = int((time.perf_counter() - self._start_time) * 1000)
                        output_data = result.get("output_data", {}) if isinstance(result, dict) else {}
                        await TaskRepository.mark_success(
                            session,
                            task,
                            output_data=output_data,
                            execution_time_ms=elapsed_ms,
                            retry_count=getattr(self.request, "retries", None),
                        )
                    if self.auto_commit:
                        await session.commit()
                    else:
                        await session.commit()
                    return result
                except Exception as exc:  # noqa: BLE001
                    await session.rollback()
                    if task:
                        await TaskRepository.mark_failed(
                            session,
                            task,
                            error_message=str(exc),
                            retry_count=getattr(self.request, "retries", None),
                        )
                        await session.commit()
                    raise
                finally:
                    self._db_session = None

        return asyncio.run(_execute())

    async def _update_retry_status(self, task_id: str, retry_count: int | None) -> None:
        if retry_count is None:
            return
        async with async_session_factory() as session:
            task = await TaskRepository.get_by_id(session, task_id)
            if task:
                await TaskRepository.mark_running(session, task, retry_count=retry_count)
                await session.commit()
