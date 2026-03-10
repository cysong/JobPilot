"""Resume tailoring logic using AgentGateway."""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from agent_configs.schemas import AnalyzedJob, TailoredResume
from app.core.llm.gateway import AgentGateway
from app.modules.applications.config import app_module_settings
from app.modules.applications.repositories.application_repo import ApplicationRepository
from app.modules.jobs.repository import JobAnalysisRepository
from app.modules.resumes.repository import DocumentRepository, ResumeRepository
from app.modules.users.repository import UserSkillRepository

logger = logging.getLogger(__name__)


async def run_resume_tailoring(
    db: AsyncSession,
    application_id: str,
    resume_id: str,
    job_id: int,
    tailoring_level: str,
    task_id: str,
    is_retry: bool = False
) -> dict:
    """
    Execute resume tailoring task.

    Always reads from source resume and creates a new versioned document.

    Args:
        resume_id: Source resume ID (not working document ID)
        is_retry: If True, indicates retry attempt (creates new version chain from previous)

    Process:
    1. Fetch Job Analysis and Source Resume.
    2. Call LLM to tailor resume content.
    3. Save tailored resume as new versioned Document.
    4. Update Application to point to new version.
    """
    # 1. Gather Context
    job_analysis_model = await JobAnalysisRepository.get_by_job_id(db, job_id)
    if not job_analysis_model:
        raise ValueError(f"Job analysis not found for job {job_id}")
    job_analysis = AnalyzedJob(
        required_skills=job_analysis_model.required_skills or [],
        preferred_skills=job_analysis_model.preferred_skills or [],
        certifications=job_analysis_model.certifications or [],
        tech_stack=job_analysis_model.tech_stack or [],
        seniority=job_analysis_model.seniority,
        key_responsibilities=job_analysis_model.key_responsibilities or [],
        experience_years=job_analysis_model.experience_years,
        education_requirement=job_analysis_model.education_requirement,
        soft_skills=job_analysis_model.soft_skills or [],
        company_culture_keywords=job_analysis_model.company_culture_keywords or [],
        hiring_priorities=job_analysis_model.hiring_priorities or [],
    )

    application = await ApplicationRepository.get_by_id(db, application_id)
    if not application:
        raise ValueError(f"Application {application_id} not found")

    # Always read from source resume (unified logic for both initial and retry)
    source_resume = await ResumeRepository.get_with_document(db, resume_id)
    if not source_resume or not source_resume.document:
        raise ValueError(
            f"Source resume {resume_id} or its document not found")

    source_content = source_resume.document.content

    if is_retry:
        logger.info(
            f"Retry mode: Reading from source resume {resume_id} for application {application_id}")
    else:
        logger.info(
            f"Reading from source resume {resume_id} for application {application_id}")

    user_skills = await UserSkillRepository.get_by_user_id(
        db, user_id=application.user_id
    )

    # Determine parent document for versioning
    # If application already has a resume document, it becomes the parent (for retry)
    # Otherwise, the source resume document is the parent (for initial creation)
    if application.resume_document_id:
        parent_doc = await DocumentRepository.get_by_id(db, application.resume_document_id)
        if not parent_doc:
            logger.warning(
                f"Previous resume document {application.resume_document_id} not found, using source as parent")
            parent_doc = source_resume.document
    else:
        parent_doc = source_resume.document
    
    # 2. Call LLM
    prompt_input = _build_tailoring_prompt(
        source_content=source_content,
        job_analysis=job_analysis,
        tailoring_level=tailoring_level,
        user_skills=user_skills,
    )

    tailored_content = await AgentGateway.get().call(
        agent_id="resume_tailor",
        input_data=prompt_input,
        context={
            "db": db,
            "task_id": task_id,
            "user_id": application.user_id
        },
    )
    
    if isinstance(tailored_content, TailoredResume):
        final_content = tailored_content.content
    elif isinstance(tailored_content, dict) and "content" in tailored_content:
        final_content = tailored_content["content"]
    else:
        final_content = str(tailored_content)

    # 3. Create new versioned Document
    # parent_doc is either the previous tailored version (retry) or source document (initial)
    change_comment = f"Retry: Tailored from source for Job {job_id} ({tailoring_level})" if is_retry else f"Tailored for Job {job_id} ({tailoring_level})"

    tailored_doc = await DocumentRepository.create_new_version(
        db=db,
        parent_document=parent_doc,
        content=final_content,
        created_by=application.user_id,
        change_comments=change_comment,
        extra_metadata={
            "application_id": application_id,
            "job_id": job_id,
            "tailoring_level": tailoring_level,
            "is_retry": is_retry,
            "task_id": task_id
        }
    )
    doc_id = tailored_doc.id

    logger.info(
        f"Created new resume document version {doc_id} "
        f"(parent: {parent_doc.id}, root: {tailored_doc.root_id}, is_retry: {is_retry})"
    )
    
    # 4. Update Application to point to new version
    application.resume_document_id = doc_id

    await db.commit()

    return {
        "output_data": {
            "resume_document_id": doc_id,
            "is_retry": is_retry,
        }
    }


def _build_tailoring_prompt(
    source_content: str,
    job_analysis: AnalyzedJob,
    tailoring_level: str,
    user_skills: list[dict],
) -> str:
    """Construct prompt for resume tailoring."""
    clipped_source = _clip_source_resume(source_content)
    selected_skills = _select_skills_for_prompt(user_skills, job_analysis)

    job_payload = _prune_empty_values(job_analysis.model_dump())
    job_json = json.dumps(job_payload, ensure_ascii=True, separators=(",", ":"))
    normalized_skills = _prune_empty_values(
        [
            {"name": skill["name"], "proficiency": skill.get("proficiency")}
            for skill in selected_skills
        ]
    )
    user_skills_json = json.dumps(
        normalized_skills, ensure_ascii=True, separators=(",", ":")
    )

    prompt = (
        f"tailoring_level: {tailoring_level}\n"
        f"job_analysis: {job_json}\n\n"
        f"user_skills: {user_skills_json}\n\n"
        f"source_resume_markdown: |\n{clipped_source}\n"
    )

    # Final guardrail for very large payloads.
    max_prompt_chars = app_module_settings.RESUME_TAILOR_MAX_PROMPT_CHARS
    if max_prompt_chars > 0 and len(prompt) > max_prompt_chars:
        overflow = len(prompt) - max_prompt_chars
        trimmed_len = max(1, len(clipped_source) - overflow - 256)
        clipped_source = clipped_source[:trimmed_len]
        prompt = (
            f"tailoring_level: {tailoring_level}\n"
            f"job_analysis: {job_json}\n\n"
            f"user_skills: {user_skills_json}\n\n"
            f"source_resume_markdown: |\n{clipped_source}\n"
        )
        logger.warning(
            "resume_tailor_prompt_trimmed",
            extra={
                "original_prompt_chars": len(prompt) + overflow,
                "final_prompt_chars": len(prompt),
            },
        )

    return prompt


def _clip_source_resume(source_content: str) -> str:
    max_chars = app_module_settings.RESUME_TAILOR_MAX_SOURCE_CHARS
    if max_chars <= 0 or len(source_content) <= max_chars:
        return source_content

    clipped = source_content[:max_chars]
    logger.warning(
        "resume_tailor_source_clipped",
        original_chars=len(source_content),
        clipped_chars=len(clipped),
    )
    return clipped


def _select_skills_for_prompt(user_skills: list[dict], job_analysis: AnalyzedJob) -> list[dict]:
    max_skills = app_module_settings.RESUME_TAILOR_MAX_SKILLS
    if max_skills <= 0:
        max_skills = 40

    jd_terms = _extract_jd_terms(job_analysis)
    scored: list[tuple[int, int, dict]] = []
    for idx, skill in enumerate(user_skills):
        raw_name = (skill.get("skill_name") or "").strip()
        if not raw_name:
            continue

        name_norm = _normalize_skill(raw_name)
        is_jd_match = 1 if name_norm in jd_terms else 0
        proficiency_score = _proficiency_score(skill.get("proficiency"))
        score = is_jd_match * 100 + proficiency_score
        scored.append(
            (
                -score,
                idx,
                {
                    "name": raw_name,
                    "proficiency": skill.get("proficiency"),
                },
            )
        )

    scored.sort(key=lambda item: (item[0], item[1]))
    selected = [item[2] for item in scored[:max_skills]]
    if len(scored) > max_skills:
        logger.info(
            "resume_tailor_skills_clipped",
            extra={
                "total_skills": len(scored),
                "selected_skills": len(selected),
            },
        )
    return selected


def _extract_jd_terms(job_analysis: AnalyzedJob) -> set[str]:
    candidates = (
        (job_analysis.required_skills or [])
        + (job_analysis.preferred_skills or [])
        + (job_analysis.tech_stack or [])
    )
    return {_normalize_skill(str(item)) for item in candidates if str(item).strip()}


def _normalize_skill(value: str) -> str:
    lowered = value.lower().strip()
    lowered = re.sub(r"[^a-z0-9+#.\-/ ]+", "", lowered)
    return re.sub(r"\s+", " ", lowered)


def _proficiency_score(value: object) -> int:
    if value is None:
        return 0
    normalized = str(value).lower().strip()
    mapping = {
        "expert": 4,
        "advanced": 3,
        "intermediate": 2,
        "beginner": 1,
    }
    return mapping.get(normalized, 0)


def _prune_empty_values(value: Any) -> Any:
    """Recursively remove empty fields to reduce prompt payload size."""
    if isinstance(value, dict):
        pruned: dict[str, Any] = {}
        for key, item in value.items():
            cleaned = _prune_empty_values(item)
            if cleaned is None:
                continue
            if cleaned == "":
                continue
            if isinstance(cleaned, (list, dict)) and not cleaned:
                continue
            pruned[key] = cleaned
        return pruned

    if isinstance(value, list):
        pruned_list = []
        for item in value:
            cleaned = _prune_empty_values(item)
            if cleaned is None:
                continue
            if cleaned == "":
                continue
            if isinstance(cleaned, (list, dict)) and not cleaned:
                continue
            pruned_list.append(cleaned)
        return pruned_list

    return value
