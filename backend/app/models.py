"""Centralized ORM model imports to ensure metadata registration."""
from app.modules.auth.models import ApiKey, User, UserSecurityToken  # noqa: F401
from app.modules.jobs.models import SeekJob, JobAnalysis, UserSavedJob, UserJobView  # noqa: F401
from app.modules.resumes.models import Resume, Document  # noqa: F401
from app.modules.applications.models import Application, OutboxEvent  # noqa: F401
from app.modules.workflow.models import TaskExecution, AICall  # noqa: F401
from app.modules.users.models import UserSkill  # noqa: F401
from app.modules.matching.models import UserJobMatch, JobMatch  # noqa: F401
from app.modules.matching.families.models import JobTitleFamily, JobRoleFamily  # noqa: F401
from app.modules.matching.labels.models import MatchLabel  # noqa: F401
from app.modules.matching.evaluation.models import (  # noqa: F401
    MatchEvalDataset,
    MatchEvalItem,
    MatchEvalPrediction,
    MatchEvalRun,
)

__all__ = [
    "User",
    "UserSecurityToken",
    "ApiKey",
    "SeekJob",
    "JobAnalysis",
    "UserSavedJob",
    "UserJobView",
    "Resume",
    "Document",
    "Application",
    "OutboxEvent",
    "TaskExecution",
    "AICall",
    "UserSkill",
    "UserJobMatch",
    "JobMatch",
    "JobTitleFamily",
    "JobRoleFamily",
    "MatchLabel",
    "MatchEvalDataset",
    "MatchEvalItem",
    "MatchEvalRun",
    "MatchEvalPrediction",
]
