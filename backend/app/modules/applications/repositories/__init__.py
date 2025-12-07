"""Application repositories."""
from app.modules.applications.repositories.aicall_repo import AICallRepository
from app.modules.applications.repositories.application_repo import ApplicationRepository
from app.modules.applications.repositories.outbox_repo import OutboxRepository

__all__ = [
    "AICallRepository",
    "ApplicationRepository",
    "OutboxRepository",
]
