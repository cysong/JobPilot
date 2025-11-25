"""Configuration for application module."""

from pydantic_settings import BaseSettings


class ApplicationModuleSettings(BaseSettings):
    """Settings for application module."""

    # Outbox consumer settings
    OUTBOX_BATCH_SIZE: int = 100
    OUTBOX_MAX_CONCURRENT: int = 5  # Maximum concurrent event processing
    OUTBOX_CONSUMER_INTERVAL_SECONDS: float = 5.0  # How often to poll for events

    # Workflow settings
    WORKFLOW_VERSION: str = "v1.0.0"
    COVER_LETTER_PROMPT_ID: str = "cover_letter_v1"
    COVER_LETTER_MODEL: str = "deepseek-chat"

    class Config:
        env_prefix = "APP_MODULE_"
        case_sensitive = True


# Global settings instance
app_module_settings = ApplicationModuleSettings()
