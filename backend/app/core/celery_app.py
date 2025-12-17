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
    broker_connection_timeout=3,            # 连接 Redis 最多等 3 秒
    broker_connection_retry_on_startup=False,  # 启动时连不上就直接报错
    broker_transport_options={
        "connect_timeout": 3,
        "socket_timeout": 5,
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
