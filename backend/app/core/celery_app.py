"""Celery application configuration for JobPilot"""
from celery import Celery
from celery.schedules import crontab

from app.core.config import settings
from app import models  # noqa: F401  # Ensure all ORM models are registered before Celery tasks load

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
)

# Discover tasks from application modules
celery_app.autodiscover_tasks([
    "app.modules.applications",
    "app.modules.jobs",  # Add jobs module for job analysis tasks
    "app.modules.resumes",  # Resume analysis tasks
    "app.modules.matching",  # Matching tasks
    "app.modules.users",  # User skill aggregation tasks
])

# Configure Celery Beat periodic tasks
celery_app.conf.beat_schedule = {
    'poll-unanalyzed-jobs': {
        'task': 'app.modules.jobs.tasks.poll_unanalyzed_jobs',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
    },
    'pull-unmatched-jobs': {
        'task': 'app.modules.matching.pull.pull_unmatched_jobs',
        'schedule': crontab(minute='*/5'),
    },
}
