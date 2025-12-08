"""Centralized ORM model imports to ensure metadata registration."""
from app.modules.auth.models import User  # noqa: F401
from app.modules.jobs.models import SeekJob, JobAnalysis  # noqa: F401
from app.modules.resumes.models import Resume, Document  # noqa: F401
from app.modules.applications.models import Application, OutboxEvent  # noqa: F401
from app.modules.workflow.models import WorkflowExecution, TaskExecution, AICall  # noqa: F401
from app.modules.users.models import UserSkill  # noqa: F401

__all__ = [
    "User",
    "SeekJob",
    "JobAnalysis",
    "Resume",
    "Document",
    "Application",
    "OutboxEvent",
    "WorkflowExecution",
    "TaskExecution",
    "AICall",
    "UserSkill",
]
