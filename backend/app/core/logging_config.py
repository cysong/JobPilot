"""Unified logging configuration for API and Celery processes."""
from __future__ import annotations

import logging
import logging.config
from logging.handlers import RotatingFileHandler
from pathlib import Path

import structlog

from app.core.config import BASE_DIR, settings

TASK_LOG_FORMAT = (
    "%(asctime)s [%(levelname)s/%(processName)s] %(name)s %(message)s "
    "service=%(service)s task_id=%(task_id)s celery_task_id=%(celery_task_id)s "
    "workflow_id=%(workflow_id)s agent_id=%(agent_id)s operation=%(operation)s"
)
API_LOG_FORMAT = (
    "%(asctime)s [%(levelname)s/%(processName)s] %(name)s %(message)s "
    "service=%(service)s"
)
DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

SERVICE_LOG_FILE_NAMES = {
    "api": "api.log",
    "celery_worker": "celery-worker.log",
    "celery_beat": "celery-beat.log",
}

_LOGGING_CONFIGURED = False


class ContextDefaultsFilter(logging.Filter):
    """Ensure formatter-required context keys always exist."""

    def __init__(self, service_name: str, include_task_context: bool = True) -> None:
        super().__init__()
        self._service_name = service_name
        self._include_task_context = include_task_context

    def filter(self, record: logging.LogRecord) -> bool:
        defaults: dict[str, str] = {
            "service": self._service_name,
        }
        if self._include_task_context:
            defaults.update(
                {
                    "task_id": "-",
                    "celery_task_id": "-",
                    "workflow_id": "-",
                    "agent_id": "-",
                    "operation": "-",
                }
            )
        for key, value in defaults.items():
            if not hasattr(record, key):
                setattr(record, key, value)
        return True


def _resolve_log_dir() -> Path:
    log_dir = Path(settings.LOG_DIR)
    if not log_dir.is_absolute():
        log_dir = BASE_DIR / log_dir
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def _resolve_log_file(service_name: str) -> Path:
    filename = SERVICE_LOG_FILE_NAMES.get(service_name, f"{service_name}.log")
    return _resolve_log_dir() / filename


def _configure_structlog() -> None:
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.KeyValueRenderer(
                key_order=["event", "agent_id", "task_id", "model", "status", "operation"]
            ),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def configure_logging(service_name: str) -> None:
    """Configure text logging with console + rotating file handlers."""
    global _LOGGING_CONFIGURED
    if _LOGGING_CONFIGURED:
        return

    log_file = _resolve_log_file(service_name)
    include_task_context = service_name != "api"
    formatter_name = "task_standard" if include_task_context else "api_standard"

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "filters": {
                "context_defaults": {
                    "()": ContextDefaultsFilter,
                    "service_name": service_name,
                    "include_task_context": include_task_context,
                }
            },
            "formatters": {
                "task_standard": {
                    "format": TASK_LOG_FORMAT,
                    "datefmt": DEFAULT_DATE_FORMAT,
                },
                "api_standard": {
                    "format": API_LOG_FORMAT,
                    "datefmt": DEFAULT_DATE_FORMAT,
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "level": settings.LOG_LEVEL,
                    "formatter": formatter_name,
                    "filters": ["context_defaults"],
                },
                "file": {
                    "()": RotatingFileHandler,
                    "level": settings.LOG_LEVEL,
                    "formatter": formatter_name,
                    "filters": ["context_defaults"],
                    "filename": str(log_file),
                    "maxBytes": settings.LOG_MAX_BYTES,
                    "backupCount": settings.LOG_BACKUP_COUNT,
                    "encoding": "utf-8",
                },
            },
            "root": {
                "level": settings.LOG_LEVEL,
                "handlers": ["console", "file"],
            },
            "loggers": {
                "uvicorn": {
                    "handlers": ["console", "file"],
                    "level": settings.LOG_LEVEL,
                    "propagate": False,
                },
                "uvicorn.error": {
                    "handlers": ["console", "file"],
                    "level": settings.LOG_LEVEL,
                    "propagate": False,
                },
                "uvicorn.access": {
                    "handlers": ["console", "file"],
                    "level": settings.LOG_LEVEL,
                    "propagate": False,
                },
                "celery": {
                    "handlers": ["console", "file"],
                    "level": settings.LOG_LEVEL,
                    "propagate": False,
                },
                "app": {
                    "handlers": ["console", "file"],
                    "level": settings.LOG_LEVEL,
                    "propagate": False,
                },
            },
        }
    )
    _configure_structlog()
    logging.captureWarnings(True)
    _LOGGING_CONFIGURED = True
