"""Applications module (application workflows and AI generation)."""

from app.core.celery_app import celery_app  # re-export for task discovery

__all__ = ["celery_app"]
