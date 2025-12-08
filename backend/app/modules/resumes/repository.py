"""Repository layer for Resume-related database operations."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.resumes.models import Resume


class ResumeRepository:
    """Data access helpers for resumes."""

    @staticmethod
    async def get_by_id(db: AsyncSession, resume_id: str) -> Optional[Resume]:
        """Fetch resume by id (without loading document)."""
        result = await db.execute(select(Resume).where(Resume.id == resume_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_with_document(db: AsyncSession, resume_id: str) -> Optional[Resume]:
        """Fetch resume with its linked document eager-loaded."""
        result = await db.execute(
            select(Resume)
            .where(Resume.id == resume_id)
            .options(selectinload(Resume.document))
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def update_analysis(
        db: AsyncSession,
        resume_id: str,
        analysis_data: dict,
        analysis_version: str,
    ) -> Resume:
        """
        Update resume analysis result and timestamps.

        Stores analysis data in resume.analysis_result field.
        """
        resume = await ResumeRepository.get_by_id(db, resume_id)
        if not resume:
            raise ValueError(f"Resume {resume_id} not found")

        now = datetime.now(timezone.utc)
        resume.target_job_titles = analysis_data.get("target_job_titles") or []
        resume.analysis_result = analysis_data
        resume.analysis_version = analysis_version
        resume.analyzed_at = now
        resume.updated_at = now

        return resume
