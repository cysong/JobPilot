"""Application configuration using Pydantic Settings"""
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List

# Get the backend directory (parent of app)
BASE_DIR = Path(__file__).resolve().parent.parent.parent
ENV_FILE = BASE_DIR / ".env"


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Database
    DATABASE_URL: str

    # Redis
    REDIS_URL: str

    # Security & Authentication
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_DAYS: int = 7  # JWT token expires in 7 days
    PASSWORD_MIN_LENGTH: int = 8
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 60
    EMAIL_VERIFY_TOKEN_EXPIRE_HOURS: int = 24
    EMAIL_CHANGE_TOKEN_EXPIRE_HOURS: int = 24
    SECURITY_TOKEN_RATE_LIMIT_WINDOW_MINUTES: int = 10
    SECURITY_TOKEN_RATE_LIMIT_MAX_COUNT: int = 3

    # User Defaults
    # Default role for new users (USER/VIP/ADMIN)
    DEFAULT_USER_ROLE: str = "USER"

    # User Limits (by role)
    USER_FORMAL_RESUME_LIMIT: int = 3  # Free users: max 3 formal resumes
    VIP_FORMAL_RESUME_LIMIT: int = 10  # VIP users: max 10 formal resumes
    # Free users: max 20 applications/month
    USER_MONTHLY_APPLICATION_LIMIT: int = 20

    # AI Configuration
    DEFAULT_LLM_PROVIDER: str = "openai"
    OPENAI_API_KEY: str
    OPENAI_API_BASE: str = "https://api.openai.com/v1"
    OPENAI_TRACING_ENABLED: bool = True
    MINIMAX_API_KEY: str = ""
    MINIMAX_API_BASE: str = "https://api.minimax.io/v1"
    MINIMAX_TRACING_ENABLED: bool = False
    OPENROUTER_API_KEY: str = ""  # Preferred for DeepSeek via OpenRouter
    OPENROUTER_API_BASE: str = "https://openrouter.ai/api/v1"

    # Job Analysis
    JOB_ANALYSIS_INTERVAL_HOURS: int = 1  # Run job analysis every N hours
    JOB_ANALYSIS_LOOKBACK_DAYS: int = 7  # Only auto-enqueue analysis for jobs listed within past N days (poll_unanalyzed_jobs)
    MAX_JOBS_PER_POLL: int = 3  # Maximum jobs to analyze per polling cycle (for testing)
    # Note: Analysis version now defined in AnalyzedJob.__version__ (agents/schemas.py)

    # Matching
    MATCH_SCORE_THRESHOLD: float = 0.6  # Minimum match score to recommend resume
    HIGH_MATCH_THRESHOLD: float = 0.9  # Threshold for "high match" badge
    MAX_JOB_MATCHES_PER_PULL: int = 100  # Maximum matching tasks to enqueue per poll cycle
    MAX_CANDIDATES_PER_JOB: int = 100  # Title-prefilter cap per job
    SKILL_MATCH_THRESHOLD: float = 40  # Minimum skill match percentage to keep a match
    MATCHING_ALGORITHM_VERSION: str = "v1.0.0"

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:5173"]

    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    APP_TIMEZONE: str = "Pacific/Auckland"
    APP_FRONTEND_URL: str = "http://localhost:5173"

    # Email
    RESEND_API_KEY: str = ""
    RESEND_FROM_EMAIL: str = ""
    RESEND_REPLY_TO_EMAIL: str = ""

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = "logs"
    LOG_MAX_BYTES: int = 10_485_760  # 10 MB per file
    LOG_BACKUP_COUNT: int = 10

    # Cache
    CACHE_ENABLED: bool = True

    # Pagination
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100

    # Workflow task retry
    TASK_RETRY_STALE_TIMEOUT_MINUTES: int = 10

    # Document Export (Resume, Cover Letter, etc.)
    # Default PDF template for all document types
    EXPORT_DEFAULT_TEMPLATE: str = "modern"

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )


# Global settings instance
settings = Settings()
