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
])
