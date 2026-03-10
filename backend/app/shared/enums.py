"""Global enumerations"""
from enum import Enum
from typing import NamedTuple, Optional


class Role(str, Enum):
    """User role enumeration"""
    USER = "USER"
    VIP = "VIP"
    ADMIN = "ADMIN"


class ApplicationStatus(str, Enum):
    """Application status enumeration"""
    PENDING = "Pending"              # Waiting for processing
    TAILORING = "Tailoring"          # AI customization in progress
    READY = "Ready"                  # Materials ready for submission
    APPLIED = "Applied"              # Application submitted
    PHONE_SCREEN = "PhoneScreen"     # Phone screening stage
    INTERVIEWING = "Interviewing"    # Interview stage
    OFFER = "Offer"                  # Offer received
    REJECTED = "Rejected"            # Application rejected
    FAILED = "Failed"                # Application failed


class TailoringLevel(str, Enum):
    """Resume tailoring intensity levels."""

    LIGHT = "light"
    MODERATE = "moderate"
    DEEP = "deep"


class TaskTypeInfo(NamedTuple):
    """
    Task type metadata container.

    This NamedTuple holds all configuration for a task type.
    Extensible: add new fields as needed (e.g., priority, tags, permissions).
    """
    value: str                          # Task type identifier (stored in DB)
    display_name: str                   # Human-readable name
    celery_task: str                    # Celery task function path
    entity: "EntityType"                # Entity type for this task
    max_retries: int = 3                # Default retry count
    timeout_seconds: Optional[int] = None  # Task timeout


class TaskType(Enum):
    """
    Task type enumeration with rich metadata.

    Each task type contains:
    - value: String identifier stored in database
    - display_name: Human-readable name for UI
    - celery_task: Full path to Celery task function
    - max_retries: Default retry count
    - timeout_seconds: Task timeout limit

    Usage:
        task_type = TaskType.JOB_ANALYSIS
        task_type.value.value              # "job_analysis"
        task_type.value.display_name       # "Job Analysis"
        task_type.value.celery_task        # "app.modules.jobs.tasks.analyze_job_async"
    """

    @classmethod
    def from_value(cls, task_type_value: Optional[str]) -> Optional["TaskType"]:
        """
        Resolve a task type string value to its corresponding TaskType enum.

        Args:
            task_type_value: The string value to look up (e.g., "job_analysis")

        Returns:
            The matching TaskType enum member, or None if not found.
        """
        for t in cls:
            if t.value.value == task_type_value:
                return t
        return None

    # Job-related tasks
    JOB_ANALYSIS = TaskTypeInfo(
        value="job_analysis",
        display_name="Job Analysis",
        celery_task="app.modules.jobs.tasks.analyze_job_task",
        entity="job",
        max_retries=3,
        timeout_seconds=300,
    )

    # Resume-related tasks
    RESUME_ANALYSIS = TaskTypeInfo(
        value="resume_analysis",
        display_name="Resume Analysis",
        celery_task="app.modules.resumes.tasks.analyze_resume_task",
        entity="resume",
        max_retries=3,
        timeout_seconds=180,
    )

    USER_JOB_MATCHING = TaskTypeInfo(
        value="user_job_matching",
        display_name="User-Job Matching",
        celery_task="app.modules.matching.tasks.match_user_recent_jobs_task",
        entity="user",
        max_retries=2,
        timeout_seconds=300,
    )

    JOB_USER_MATCHING = TaskTypeInfo(
        value="job_user_matching",
        display_name="Job-User Matching",
        celery_task="app.modules.matching.tasks.calculate_job_user_matches_task",
        entity="job",
        max_retries=3,
        timeout_seconds=600,
    )

    # Cover Letter workflow tasks
    APPLICATION_INITIALIZATION = TaskTypeInfo(
        value="application_initialization",
        display_name="Application Initialization",
        celery_task="app.modules.applications.tasks.application_initialization_task",
        entity="application",
        max_retries=3,
        timeout_seconds=60,
    )

    RESUME_TAILORING = TaskTypeInfo(
        value="resume_tailoring",
        display_name="Resume Tailoring",
        celery_task="app.modules.applications.tasks.resume_tailoring_task",
        entity="application",
        max_retries=2,
        timeout_seconds=300,
    )

    COVER_LETTER_GENERATION = TaskTypeInfo(
        value="cover_letter_generation",
        display_name="Cover Letter - Generation",
        celery_task="app.modules.applications.tasks.cover_letter_generation_task",
        entity="application",
        max_retries=2,
        timeout_seconds=600,
    )

    # User skill aggregation task
    SKILL_AGGREGATION = TaskTypeInfo(
        value="skill_aggregation",
        display_name="Skill Aggregation",
        celery_task="app.modules.users.tasks.aggregate_user_skills_task",
        entity="resume",
        max_retries=2,
        timeout_seconds=180,
    )

    # Generic tasks (reserved for future use)
    DOCUMENT_GENERATION = TaskTypeInfo(
        value="document_generation",
        display_name="Document Generation",
        celery_task="app.modules.documents.tasks.generate_document_task",
        entity="application",
        max_retries=2,
    )

    DOCUMENT_QUALITY_CHECK = TaskTypeInfo(
        value="document_quality_check",
        display_name="Document Quality Check",
        celery_task="app.modules.quality.tasks.check_quality_task",
        entity="application",
        max_retries=1,
        timeout_seconds=60,
    )


class TaskStatus(str, Enum):
    """Individual task execution status"""
    PENDING = "Pending"
    RUNNING = "Running"
    SUCCESS = "Success"
    FAILED = "Failed"
    RETRY = "Retry"


class AICallStatus(str, Enum):
    """AI call execution status"""
    PENDING = "Pending"
    SUCCESS = "Success"
    FAILED = "Failed"


class DocumentFormat(str, Enum):
    """Document format enumeration"""
    MARKDOWN = "Markdown"
    HTML = "HTML"
    PLAIN_TEXT = "PlainText"


class ProficiencyLevel(str, Enum):
    """Skill proficiency level enumeration"""
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


class EntityType(str, Enum):
    """Entity types for task executions."""
    JOB = "job"
    RESUME = "resume"
    APPLICATION = "application"
