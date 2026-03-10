"""Celery task base classes for async execution and DB-backed tracking."""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from celery import Task
from celery.exceptions import Ignore, Retry
from celery.utils.time import get_exponential_backoff_interval
from openai import (
    AuthenticationError,
    BadRequestError,
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    UnprocessableEntityError,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory
from app.core.celery_lifecycle import get_worker_loop
from app.modules.workflow.repositories import TaskRepository
from app.shared.enums import TaskStatus

logger = logging.getLogger(__name__)


class AsyncBaseTask(Task):
    """Async-aware Celery task that injects `self.db` session."""

    abstract = True
    auto_commit = False
    _db_session: AsyncSession | None = None

    # Native Celery retry configuration
    autoretry_for = (Exception,)    # Retry on any exception
    dont_autoretry_for = (
        ValueError,
        BadRequestError,           # 400: invalid params/content for the request
        AuthenticationError,       # 401: API key / auth config issue
        PermissionDeniedError,     # 403: key lacks permission
        NotFoundError,             # 404: model/resource not found
        ConflictError,             # 409: conflicting request state
        UnprocessableEntityError,  # 422: semantic validation failure
    )
    max_retries = 3                  # Maximum retry attempts (default)
    retry_backoff = True             # Exponential backoff between retries
    retry_backoff_max = 600          # Max backoff time (10 minutes)
    retry_jitter = True              # Add random jitter to prevent thundering herd

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        if asyncio.iscoroutinefunction(self.run):
            return self._run_async_task(*args, **kwargs)

        # Fallback: Celery may wrap run so iscoroutinefunction can return False.
        # If the parent __call__ yields a coroutine, run it with a managed session.
        result = super().__call__(*args, **kwargs)
        if asyncio.iscoroutine(result):
            async def _execute():
                async with async_session_factory() as session:
                    self._db_session = session
                    try:
                        retval = await result
                        if self.auto_commit:
                            await session.commit()
                        return retval
                    except Exception as exc:
                        await session.rollback()
                        # Manual autoretry support for async tasks
                        self._handle_async_autoretry(exc)
                        raise
                    finally:
                        self._db_session = None

            return get_worker_loop().run_until_complete(_execute())
        return result

    def _run_async_task(self, *args: Any, **kwargs: Any) -> Any:
        async def _execute():
            async with async_session_factory() as session:
                self._db_session = session
                try:
                    result = await self.run(*args, **kwargs)
                    if self.auto_commit:
                        await session.commit()
                    return result
                except Exception as exc:
                    await session.rollback()
                    # Manual autoretry support for async tasks (Celery's autoretry_for doesn't work with async)
                    # This follows Celery's design by reusing self.retry() method and configuration
                    self._handle_async_autoretry(exc)
                    raise
                finally:
                    self._db_session = None

        return get_worker_loop().run_until_complete(_execute())

    def _handle_async_autoretry(self, exc: Exception) -> None:
        """
        Handle autoretry logic for async tasks.

        Celery's built-in autoretry_for doesn't work with async tasks because:
        1. The autoretry wrapper is synchronous and wraps the run method
        2. Calling an async function returns a coroutine without executing it
        3. Exceptions are only raised when the coroutine is awaited
        4. By that time, we're outside the autoretry wrapper's try-except

        This method replicates Celery's autoretry logic by:
        - Using task's autoretry_for/dont_autoretry_for configuration
        - Calling self.retry() to leverage Celery's retry mechanism
        - Using get_exponential_backoff_interval() for backoff calculation

        References:
        - https://github.com/celery/celery/blob/main/celery/app/autoretry.py
        - https://github.com/celery/celery/issues/7874
        """
        # Ignore and Retry exceptions should never be autoretried
        if isinstance(exc, (Ignore, Retry)):
            return

        if not self._should_retry_exception(exc):
            return

        # Get autoretry configuration from task attributes
        autoretry_for = getattr(self, 'autoretry_for', ())
        dont_autoretry_for = getattr(self, 'dont_autoretry_for', ())

        # Check if exception should be excluded from autoretry
        if dont_autoretry_for and isinstance(exc, dont_autoretry_for):
            return

        # Check if exception matches autoretry_for
        if not autoretry_for or not isinstance(exc, autoretry_for):
            return

        # Build retry kwargs following Celery's autoretry behavior
        retry_kwargs = getattr(self, 'retry_kwargs', {}).copy()

        # Calculate exponential backoff if configured
        retry_backoff = getattr(self, 'retry_backoff', False)
        if retry_backoff:
            retry_backoff_max = int(getattr(self, 'retry_backoff_max', 600))
            retry_jitter = getattr(self, 'retry_jitter', True)
            retry_kwargs['countdown'] = get_exponential_backoff_interval(
                factor=int(max(1.0, float(retry_backoff))),
                retries=self.request.retries,
                maximum=retry_backoff_max,
                full_jitter=retry_jitter
            )

        # Call Celery's retry method, which will raise Retry exception
        # The throw=True (default) causes it to raise, which stops propagation
        raise self.retry(exc=exc, **retry_kwargs)

    def _should_retry_exception(self, exc: Exception) -> bool:
        """
        Return True when an exception is likely transient.

        Current policy:
        - Retry transient infra/API failures (timeouts, connection, 5xx, 429).
        - Do not retry deterministic request/data errors (validation, auth, missing data).
        """
        return not isinstance(exc, getattr(self, "dont_autoretry_for", ()))

    @property
    def db(self) -> AsyncSession:
        if not self._db_session:
            raise RuntimeError("Database session is not available")
        return self._db_session


class DBTrackingTask(AsyncBaseTask):
    """
    Async task base with automatic task_executions state tracking.
    Uses native Celery hooks for lifecycle management and automatic retries.

    Ensures all tasks inherit proper retry configuration from AsyncBaseTask.
    """

    abstract = True

    # Explicitly inherit retry configuration from AsyncBaseTask
    # This ensures tasks don't accidentally override these settings
    autoretry_for = (Exception,)
    max_retries = 3
    retry_backoff = True
    retry_backoff_max = 600
    retry_jitter = True

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        # Capture start time for duration calculation
        self._start_time = time.perf_counter()
        return super().__call__(*args, **kwargs)

    def before_start(self, task_id, args, kwargs):
        """Called before the task starts. Mark as RUNNING."""
        db_task_id = kwargs.get("task_id")
        if db_task_id:
            try:
                # Use current retry count from Celery request (0 for first attempt, increments on retry)
                current_retry_count = getattr(self.request, "retries", 0)
                get_worker_loop().run_until_complete(
                    self._update_status(db_task_id, "RUNNING", retry_count=current_retry_count)
                )
                logger.info(
                    f"Task started: {self.name}",
                    extra={
                        "task_id": db_task_id,
                        "celery_task_id": task_id,
                        "retry_count": current_retry_count,
                    }
                )
            except Exception as exc:
                # Critical: Don't let hook failures prevent task execution
                logger.warning(
                    f"Failed to update task status in before_start: {exc}",
                    extra={
                        "task_id": db_task_id,
                        "celery_task_id": task_id,
                    },
                    exc_info=True
                )
        return super().before_start(task_id, args, kwargs)

    def on_success(self, retval, task_id, args, kwargs):
        """Called on success. Mark as SUCCESS."""
        db_task_id = kwargs.get("task_id")
        if db_task_id:
            elapsed_ms = int((time.perf_counter() - getattr(self, "_start_time", time.perf_counter())) * 1000)
            output_data = retval.get("output_data", {}) if isinstance(retval, dict) else {}

            try:
                get_worker_loop().run_until_complete(
                    self._mark_success(db_task_id, output_data, elapsed_ms)
                )
                logger.info(
                    f"Task completed successfully: {self.name}",
                    extra={
                        "task_id": db_task_id,
                        "celery_task_id": task_id,
                        "execution_time_ms": elapsed_ms,
                    }
                )
            except Exception as exc:
                # Log error but don't fail the task that already succeeded
                logger.error(
                    f"Failed to mark task as success (task succeeded but status update failed): {exc}",
                    extra={
                        "task_id": db_task_id,
                        "celery_task_id": task_id,
                    },
                    exc_info=True
                )
        return super().on_success(retval, task_id, args, kwargs)

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Called when the task fails (retries exhausted). Mark as FAILED."""
        db_task_id = kwargs.get("task_id")
        if db_task_id:
            try:
                get_worker_loop().run_until_complete(
                    self._mark_failed(db_task_id, str(exc))
                )
                logger.error(
                    f"Task failed permanently: {self.name}",
                    extra={
                        "task_id": db_task_id,
                        "celery_task_id": task_id,
                        "error": str(exc),
                        "retries": getattr(self.request, "retries", 0),
                    },
                    exc_info=True
                )
            except Exception as update_exc:
                # Log error but don't suppress the original task failure
                logger.error(
                    f"Failed to mark task as failed (double error): {update_exc}",
                    extra={
                        "task_id": db_task_id,
                        "celery_task_id": task_id,
                        "original_error": str(exc),
                    },
                    exc_info=True
                )
        return super().on_failure(exc, task_id, args, kwargs, einfo)

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """
        Called when the task is being retried.

        Note: We only log here, not update DB. The retry_count will be updated
        in before_start hook when the retried task actually starts execution.
        This avoids duplicate DB writes for the same retry.
        """
        db_task_id = kwargs.get("task_id")
        retry_count = getattr(self.request, "retries", 0) + 1  # Next retry number
        if db_task_id:
            logger.warning(
                f"Task retry {retry_count} triggered: {self.name}",
                extra={
                    "task_id": db_task_id,
                    "celery_task_id": task_id,
                    "retry_count": retry_count,
                    "max_retries": self.max_retries,
                    "error": str(exc),
                }
            )
        return super().on_retry(exc, task_id, args, kwargs, einfo)

    async def _update_status(self, task_id: str, status: str, retry_count: int = None):
        async with async_session_factory() as session:
            task = await TaskRepository.get_by_id(session, task_id)
            if task:
                await TaskRepository.mark_running(
                    session, 
                    task, 
                    celery_task_id=self.request.id, 
                    worker_id=self.request.hostname,
                    retry_count=retry_count
                )
                await session.commit()

    async def _mark_success(self, task_id: str, output_data: dict, elapsed_ms: int):
        async with async_session_factory() as session:
            task = await TaskRepository.get_by_id(session, task_id)
            if task:
                await TaskRepository.mark_success(
                    session,
                    task,
                    output_data=output_data,
                    execution_time_ms=elapsed_ms,
                    retry_count=getattr(self.request, "retries", 0)
                )
                await session.commit()

    async def _mark_failed(self, task_id: str, error_message: str):
        """
        Mark task as FAILED only if not already in SUCCESS state.

        This protects against chain transition errors that occur after
        a task successfully completes. Such errors should not overwrite
        the SUCCESS status of the current task.
        """
        async with async_session_factory() as session:
            task = await TaskRepository.get_by_id(session, task_id)
            if task:
                # Don't overwrite SUCCESS status
                # This handles errors from chain transitions or other post-completion issues
                if task.status == TaskStatus.SUCCESS:
                    logger.warning(
                        "Attempted to mark SUCCESS task as FAILED (race condition detected)",
                        extra={
                            "task_id": task_id,
                            "current_status": task.status.value,
                            "error_message": error_message,
                            "celery_task_id": self.request.id if hasattr(self, "request") else None,
                        }
                    )
                    return

                await TaskRepository.mark_failed(
                    session,
                    task,
                    error_message=error_message,
                    retry_count=getattr(self.request, "retries", 0)
                )
                await session.commit()

                logger.info(
                    "Task marked as FAILED",
                    extra={
                        "task_id": task_id,
                        "retry_count": task.retry_count,
                        "error_message": error_message[:200],  # Truncate long errors
                    }
                )
