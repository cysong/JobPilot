"""Celery application configuration for JobPilot"""
from celery import Celery

from app.core.config import settings

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
)

# Discover tasks from application modules
celery_app.autodiscover_tasks([
    "app.modules.applications",
])
