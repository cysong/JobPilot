"""Resume module configuration."""

from pydantic import BaseModel


class ResumeModuleSettings(BaseModel):
    """Static resume-module settings kept out of environment variables."""

    TARGET_JOB_TITLES_LIMIT: int = 10


resume_module_settings = ResumeModuleSettings()
