import os

import pytest

os.environ["DEBUG"] = "false"

from app.core.exceptions import BadRequestError
from app.modules.resumes.config import resume_module_settings
from app.modules.resumes.service import ResumeService


def test_normalize_target_job_titles_deduplicates_and_strips():
    titles = [
        " Backend Developer ",
        "backend developer",
        "",
        "  ",
        "Software Engineer",
    ]

    normalized = ResumeService._normalize_target_job_titles(titles, max_titles=5)

    assert normalized == ["Backend Developer", "Software Engineer"]


def test_normalize_target_job_titles_rejects_over_limit():
    titles = [
        "Backend Developer",
        "Software Engineer",
        "Full Stack Developer",
        "Data Engineer",
        "DevOps Engineer",
        "Platform Engineer",
        "Product Engineer",
        "Site Reliability Engineer",
        "QA Engineer",
        "Mobile Developer",
        "AI Engineer",
    ]

    limit = resume_module_settings.TARGET_JOB_TITLES_LIMIT
    with pytest.raises(BadRequestError, match=f"At most {limit} target job titles are allowed."):
        ResumeService._normalize_target_job_titles(titles, max_titles=limit)
