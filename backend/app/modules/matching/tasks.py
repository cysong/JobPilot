"""Celery tasks for user-job matching."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.celery_app import celery_app
from app.core.config import settings
from app.modules.jobs.repository import JobAnalysisRepository, JobRepository
from app.modules.matching.repository import UserJobMatchRepository
from app.modules.matching.pull import pull_unmatched_jobs  # ensure Celery registers periodic pull task
from app.modules.matching.service import (
    calculate_skill_match_score,
    find_best_resume_for_user,
    prefilter_candidates_by_title,
    get_recent_jobs_with_analysis,
    user_has_title_target,
)
from app.modules.resumes.repository import ResumeRepository
from app.modules.users.repository import UserSkillRepository
from app.modules.workflow import AsyncBaseTask, DBTrackingTask
from agent_configs.schemas import MatchAnalysis
from app.core.llm.gateway import AgentGateway


@celery_app.task(base=DBTrackingTask, bind=True)
async def calculate_job_user_matches_task(self, task_id: str, job_analysis_id: int) -> dict:
    """Match users for a single job analysis."""
    return await _calculate(db=self.db, task_id=task_id, job_analysis_id=job_analysis_id)


@celery_app.task(base=DBTrackingTask, bind=True)
async def match_user_recent_jobs_task(self, task_id: str, user_id: int, days: int = 30) -> dict:
    """Match a single user against recent jobs (listed within days) that already have analyses."""
    return await _match_user(db=self.db, task_id=task_id, user_id=user_id, days=days)


async def _calculate(db: AsyncSession, *, task_id: str, job_analysis_id: int) -> dict:
    analysis = await JobAnalysisRepository.get_by_id(db, job_analysis_id)
    if not analysis:
        return {"status": "job_analysis_not_found", "job_analysis_id": job_analysis_id}
    analyses = [analysis]
    total_candidates = 0
    total_after_title = 0
    total_after_skill = 0
    ai_submitted = 0

    # Only `normalised_role_title` is used below; brief load avoids pulling
    # content + the JobAnalysis relationship on every matching task run.
    job = await JobRepository.get_brief(db, analysis.job_id)
    if job is None:
        return {"status": "job_not_found", "job_id": analysis.job_id}

    for job_analysis in analyses:
        job_title = job_analysis.normalized_job_title or job.normalised_role_title
        if not job_title:
            continue

        # Phase 0: title prefilter
        candidates = await prefilter_candidates_by_title(
            db,
            normalized_job_title=job_title.lower(),
            max_candidates=settings.MAX_CANDIDATES_PER_JOB,
        )
        total_candidates += len(candidates)
        total_after_title += len(candidates)

        for user_id in candidates:
            user_skills = await UserSkillRepository.get_by_user_id(db, user_id=user_id)
            skill_score, skill_details = calculate_skill_match_score(
                user_skills=user_skills,
                job_analysis=job_analysis,
                required_weight=0.7,
                preferred_weight=0.2,
                soft_weight=0.1,
            )
            if skill_score < settings.SKILL_MATCH_THRESHOLD:
                continue

            total_after_skill += 1

            resume_id, resume_score, resume_details = await find_best_resume_for_user(
                db=db,
                user_id=user_id,
                job_analysis=job_analysis,
            )

            match = await UserJobMatchRepository.upsert(
                db=db,
                user_id=user_id,
                job_id=job_analysis.job_id,
                skill_match_score=skill_score,
                skill_match_details=skill_details,
                recommended_resume_id=resume_id,
                resume_match_score=resume_score if resume_id else None,
                resume_match_details=resume_details if resume_id else None,
                matching_algorithm_version=MatchAnalysis.__version__,
            )
            await db.commit()

            if resume_id:
                analyze_match_with_ai_task.delay(
                    task_id=task_id,
                    match_id=match.id,
                    user_id=user_id,
                    job_id=job_analysis.job_id,
                    resume_id=resume_id,
                )
                ai_submitted += 1

    return {
        "jobs": len(analyses),
        "candidates_prefilter": total_candidates,
        "after_title_filter": total_after_title,
        "after_skill_filter": total_after_skill,
        "ai_submitted": ai_submitted,
    }


@celery_app.task(
    base=AsyncBaseTask,
    bind=True,
    ignore_result=True
)
async def analyze_match_with_ai_task(
    self,
    task_id: str,
    match_id: str,
    user_id: int,
    job_id: int,
    resume_id: str,
):
    """Run AI review for a match."""
    try:
        job_analysis = await JobAnalysisRepository.get_by_job_id(self.db, job_id)
        # Only title / advertiser_name / location_label are used below.
        job = await JobRepository.get_brief(self.db, job_id)
        resume = await ResumeRepository.get_by_id(self.db, resume_id)
        user_skills = await UserSkillRepository.get_by_user_id(self.db, user_id=user_id)

        if not all([job_analysis, job, resume, resume.analysis_result, user_skills]):
            raise ValueError("Missing required data for AI analysis")

        payload = {
            "job": {
                "title": job.title,
                "advertiser_name": job.advertiser_name,
                "location_label": job.location_label,
            },
            "job_analysis": job_analysis,
            "resume_analysis": resume.analysis_result,
            "user_skills": user_skills,
        }
        result = await AgentGateway.get().call(
            agent_id="match_analyzer",
            input_data=json.dumps(payload),
            context={"db": self.db, "task_id": task_id, "user_id": user_id},
        )
        ai_result = result.model_dump() if isinstance(result, MatchAnalysis) else result

        await UserJobMatchRepository.update_ai_analysis(
            db=self.db,
            match_id=match_id,
            ai_match_score=ai_result.get("ai_match_score", 0),
            ai_analysis=ai_result,
            ai_analyzed_at=datetime.now(timezone.utc),
        )
        await self.db.commit()
    except Exception as exc:  # noqa: BLE001
        if self._should_retry_exception(exc) and self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))
        raise


async def _match_user(db: AsyncSession, *, task_id: str, user_id: int, days: int) -> dict:
    job_analyses = await get_recent_jobs_with_analysis(db, days=days)
    processed = 0
    ai_submitted = 0

    user_skills = await UserSkillRepository.get_by_user_id(db, user_id=user_id)

    for ja in job_analyses:
        if not ja.normalized_job_title:
            continue
        if not await user_has_title_target(db, user_id=user_id, normalized_job_title=ja.normalized_job_title.lower()):
            continue

        skill_score, skill_details = calculate_skill_match_score(
            user_skills=user_skills,
            job_analysis=ja,
            required_weight=0.7,
            preferred_weight=0.2,
            soft_weight=0.1,
        )
        if skill_score < settings.SKILL_MATCH_THRESHOLD:
            continue

        resume_id, resume_score, resume_details = await find_best_resume_for_user(
            db=db,
            user_id=user_id,
            job_analysis=ja,
        )

        match = await UserJobMatchRepository.upsert(
            db=db,
            user_id=user_id,
            job_id=ja.job_id,
            skill_match_score=skill_score,
            skill_match_details=skill_details,
            recommended_resume_id=resume_id,
            resume_match_score=resume_score if resume_id else None,
            resume_match_details=resume_details if resume_id else None,
            matching_algorithm_version=MatchAnalysis.__version__,
        )
        await db.commit()
        processed += 1

        if resume_id:
            analyze_match_with_ai_task.delay(
                task_id=task_id,
                match_id=match.id,
                user_id=user_id,
                job_id=ja.job_id,
                resume_id=resume_id,
            )
            ai_submitted += 1

    return {"jobs_considered": len(job_analyses), "processed": processed, "ai_submitted": ai_submitted}
