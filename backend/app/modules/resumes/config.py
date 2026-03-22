"""Resume module configuration."""

from pydantic import BaseModel


class ResumeModuleSettings(BaseModel):
    """Static resume-module settings kept out of environment variables."""

    TARGET_JOB_TITLES_LIMIT: int = 10
    TARGET_JOB_TITLE_MIN_JOB_COUNT: int = 3


resume_module_settings = ResumeModuleSettings()
