"""Application configuration using Pydantic Settings"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


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

    # User Defaults
    # Default role for new users (USER/VIP/ADMIN)
    DEFAULT_USER_ROLE: str = "USER"

    # User Limits (by role)
    USER_FORMAL_RESUME_LIMIT: int = 3  # Free users: max 3 formal resumes
    VIP_FORMAL_RESUME_LIMIT: int = 10  # VIP users: max 10 formal resumes
    # Free users: max 20 applications/month
    USER_MONTHLY_APPLICATION_LIMIT: int = 20

    # AI Configuration
    OPENAI_API_KEY: str
    OPENAI_API_BASE: str = "https://api.openai.com/v1"
    OPENROUTER_API_KEY: str = ""  # Preferred for DeepSeek via OpenRouter
    OPENROUTER_API_BASE: str = "https://openrouter.ai/api/v1"

    # Job Analysis
    JOB_ANALYSIS_INTERVAL_HOURS: int = 1  # Run job analysis every N hours
    JOB_ANALYSIS_LOOKBACK_DAYS: int = 7  # Analyze jobs from past N days

    # Matching
    MATCH_SCORE_THRESHOLD: float = 0.6  # Minimum match score to recommend resume
    HIGH_MATCH_THRESHOLD: float = 0.9  # Threshold for "high match" badge

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:5173"]

    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = False

    # Pagination
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100

    # Document Export (Resume, Cover Letter, etc.)
    # Default PDF template for all document types
    EXPORT_DEFAULT_TEMPLATE: str = "modern"

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore"
    )


# Global settings instance
settings = Settings()
