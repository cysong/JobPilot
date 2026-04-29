"""Repository layer for Resume-related database operations."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from uuid import uuid4
import hashlib

from app.modules.resumes.models import Resume, Document


class DocumentRepository:
    """Repository for Document operations."""

    @staticmethod
    def _calculate_content_hash(content: str) -> str:
        """Calculate SHA-256 hash of content."""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    @staticmethod
    async def create(db: AsyncSession, document: Document) -> Document:
        """Create a new document (low-level)."""
        db.add(document)
        return document

    @staticmethod
    async def create_new_version(
        db: AsyncSession,
        parent_document: Document,
        content: str,
        created_by: int,
        change_comments: Optional[str] = None,
        extra_metadata: Optional[dict] = None,
    ) -> Document:
        """
        Create a new version of an existing document.
        
        Inherits root_id, format.
        Sets parent_id to parent_document.id.
        Auto-generates id and content_hash.
        """
        new_id = str(uuid4())
        content_hash = DocumentRepository._calculate_content_hash(content)
        
        # Merge metadata if needed, or just use new? 
        # Usually we might want to keep some, but arguments say 'extra_metadata'.
        # Let's start with parent's metadata and update with new.
        final_metadata = (parent_document.extra_metadata or {}).copy()
        if extra_metadata:
            final_metadata.update(extra_metadata)

        new_doc = Document(
            id=new_id,
            root_id=parent_document.root_id,
            parent_id=parent_document.id,
            format=parent_document.format,
            content=content,
            content_hash=content_hash,
            change_comments=change_comments,
            extra_metadata=final_metadata,
            created_by=created_by
        )
        
        db.add(new_doc)
        return new_doc

    @staticmethod
    async def get_by_id(db: AsyncSession, document_id: str) -> Optional[Document]:
        """Get document by ID."""
        result = await db.execute(select(Document).where(Document.id == document_id))
        return result.scalar_one_or_none()



class ResumeRepository:
    """Data access helpers for resumes."""

    @staticmethod
    async def get_by_id(db: AsyncSession, resume_id: str) -> Optional[Resume]:
        """Fetch resume by id (without loading document)."""
        result = await db.execute(select(Resume).where(Resume.id == resume_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_ids_map(
        db: AsyncSession,
        resume_ids: list[str],
    ) -> dict[str, Resume]:
        """Batch fetch resumes by id, returns ``{resume_id: Resume}``.

        Use this to avoid N+1 queries when materializing a match list.
        """
        if not resume_ids:
            return {}
        result = await db.execute(
            select(Resume).where(Resume.id.in_(resume_ids))
        )
        return {resume.id: resume for resume in result.scalars().all()}

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
        merged_target_job_titles: list[str] | None = None,
    ) -> Resume:
        """
        Update resume analysis result and timestamps.

        Stores analysis data in resume.analysis_result field.
        """
        resume = await ResumeRepository.get_by_id(db, resume_id)
        if not resume:
            raise ValueError(f"Resume {resume_id} not found")

        now = datetime.now(timezone.utc)
        if merged_target_job_titles is not None:
            resume.target_job_titles = merged_target_job_titles
        resume.analysis_result = analysis_data
        resume.analysis_version = analysis_version
        resume.analyzed_at = now
        resume.updated_at = now

        return resume
