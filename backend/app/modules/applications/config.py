"""Configuration for application module."""

from pydantic_settings import BaseSettings


class ApplicationModuleSettings(BaseSettings):
    """Settings for application module."""

    # Outbox consumer settings
    OUTBOX_BATCH_SIZE: int = 100
    OUTBOX_MAX_CONCURRENT: int = 5  # Maximum concurrent event processing
    OUTBOX_CONSUMER_INTERVAL_SECONDS: float = 5.0  # How often to poll for events

    # Cover letter generation settings
    MAX_REVIEW_ITERATIONS: int = 2
    REVIEW_PASS_SCORE: float = 8.0

    # Resume tailoring prompt controls (to prevent oversized prompts / runaway turns)
    RESUME_TAILOR_MAX_SOURCE_CHARS: int = 20_000
    RESUME_TAILOR_MAX_SKILLS: int = 40
    RESUME_TAILOR_MAX_PROMPT_CHARS: int = 35_000

    class Config:
        env_prefix = "APP_MODULE_"
        case_sensitive = True


# Global settings instance
app_module_settings = ApplicationModuleSettings()
