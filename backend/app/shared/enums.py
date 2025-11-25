"""Global enumerations"""
from enum import Enum


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


class WorkflowStatus(str, Enum):
    """Workflow execution status"""
    PENDING = "Pending"
    RUNNING = "Running"
    COMPLETED = "Completed"
    FAILED = "Failed"
    CANCELLED = "Cancelled"


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
    BEGINNER = "Beginner"
    INTERMEDIATE = "Intermediate"
    ADVANCED = "Advanced"
    EXPERT = "Expert"
