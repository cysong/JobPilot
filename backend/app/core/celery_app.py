"""Celery application configuration for JobPilot"""
import logging
import time
from celery import Celery
from celery.schedules import crontab
from celery.signals import (
    task_failure,
    task_postrun,
    task_prerun,
    task_retry,
    task_success,
)

from app.core import metrics
from app.core.config import settings
from app import models  # noqa: F401  # Ensure all ORM models are registered before Celery tasks load

logger = logging.getLogger(__name__)

# Initialize Celery using Redis for broker and backend
celery_app = Celery(
    "jobpilot",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

# Basic serialization and timezone settings
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    worker_disable_rate_limits=True,
    broker_connection_timeout=3,            # Connection timeout to Redis (3 seconds)
    broker_connection_retry_on_startup=False,  # Error will be raised if connection fails
    broker_connection_max_retries=100,
    broker_transport_options={
        "connect_timeout": 3,
        "socket_timeout": 5,
        "retry_on_timeout": True,
        "health_check_interval": 10,
    },
    result_backend_transport_options={
        "connect_timeout": 3,
        "socket_timeout": 5,
    },
    # Keep the application's logging config (file handlers + formatters)
    worker_hijack_root_logger=False,
)

# Discover tasks from application modules
celery_app.autodiscover_tasks([
    "app.modules.applications",
    "app.modules.jobs",  # Add jobs module for job analysis tasks
    "app.modules.resumes",  # Resume analysis tasks
    "app.modules.matching",  # Matching tasks
    "app.modules.users",  # User skill aggregation tasks
])

# Configure Celery Beat periodic tasks.
# When `DISABLE_BEAT_TASKS=true` is set in the environment, beat is started
# with an empty schedule — the process stays alive but never dispatches
# anything. Toggling requires a beat restart (the schedule is read at
# startup, not per tick).
_DEFAULT_BEAT_SCHEDULE = {
    'poll-unanalyzed-jobs': {
        'task': 'app.modules.jobs.tasks.poll_unanalyzed_jobs',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
    },
    # DISABLED: job-user matching is paused. Uncomment the entry below to
    # re-enable the periodic dispatcher (every 5 minutes).
    # 'pull-unmatched-jobs': {
    #     'task': 'app.modules.matching.pull.pull_unmatched_jobs',
    #     'schedule': crontab(minute='*/5'),
    # },
}

celery_app.conf.beat_schedule = (
    {} if settings.DISABLE_BEAT_TASKS else _DEFAULT_BEAT_SCHEDULE
)
if settings.DISABLE_BEAT_TASKS:
    logger.warning(
        "Celery beat schedule disabled via DISABLE_BEAT_TASKS=true; "
        "no periodic tasks will be dispatched."
    )


# ===== Task Monitoring Signals =====

# Per-task start timestamps for duration measurement. prerun adds, postrun pops.
# Bounded by concurrent in-flight tasks per worker process (typically <100).
_task_start_times: dict[str, float] = {}


@task_prerun.connect
def on_task_prerun_signal(task_id=None, task=None, **kwargs):
    """Record task start time for duration measurement."""
    if task_id:
        _task_start_times[task_id] = time.monotonic()


@task_postrun.connect
def on_task_postrun_signal(task_id=None, task=None, **kwargs):
    """Observe task duration when execution finishes (success or failure)."""
    start = _task_start_times.pop(task_id, None) if task_id else None
    if start is None or task is None:
        return
    duration = time.monotonic() - start
    metrics.celery_task_duration_seconds.labels(task_name=task.name).observe(duration)


@task_retry.connect
def on_task_retry_signal(sender=None, task_id=None, exception=None, **kwargs):
    """
    Global signal handler for task retries.
    Logs all retry attempts and emits a Prometheus counter.
    """
    task_name = sender.name if sender else "Unknown"
    retries = sender.request.retries if sender and hasattr(sender, "request") else 0

    metrics.celery_task_total.labels(task_name=task_name, event="retry").inc()

    logger.warning(
        f"Task retry triggered: {task_name}",
        extra={
            "event": "task_retry",
            "task_name": task_name,
            "celery_task_id": task_id,
            "exception": str(exception),
            "retry_count": retries,
            "max_retries": sender.max_retries if sender else None,
        }
    )


@task_failure.connect
def on_task_failure_signal(sender=None, task_id=None, exception=None, **kwargs):
    """
    Global signal handler for permanent task failures.
    Logs when tasks fail after exhausting all retries.
    """
    task_name = sender.name if sender else "Unknown"
    retries = sender.request.retries if sender and hasattr(sender, "request") else 0

    metrics.celery_task_total.labels(task_name=task_name, event="failure").inc()

    logger.error(
        f"Task failed permanently: {task_name}",
        extra={
            "event": "task_failed",
            "task_name": task_name,
            "celery_task_id": task_id,
            "exception": str(exception),
            "retry_count": retries,
        },
        exc_info=True
    )


@task_success.connect
def on_task_success_signal(sender=None, **kwargs):
    """
    Global signal handler for task success.
    Logs successful task completions for monitoring.
    """
    task_name = sender.name if sender else "Unknown"
    task_id = sender.request.id if sender and hasattr(sender, "request") else None

    metrics.celery_task_total.labels(task_name=task_name, event="success").inc()

    logger.info(
        f"Task succeeded: {task_name}",
        extra={
            "event": "task_success",
            "task_name": task_name,
            "celery_task_id": task_id,
        }
    )
