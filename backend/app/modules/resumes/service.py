"""
Resume service layer - business logic for resume operations.
"""
import hashlib
from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import (
    BadRequestError,
    BusinessError,
    JobPilotException,
    NotFoundError,
)
from app.core.response_codes import ResponseCode
from app.modules.resumes.models import Document, DocumentFormat, Resume, ResumeSkill
from app.modules.resumes.repository import ResumeRepository, DocumentRepository
from app.modules.resumes.schemas import ResumeCreate, ResumeUpdate
from app.modules.workflow.service import TaskService, TaskSubmissionSpec
from app.shared.enums import TaskType, ProficiencyLevel
from app.core.config import settings



class ResumeService:
    """Service class for Resume-related operations."""

    @staticmethod
    async def create_resume(
        db: AsyncSession, user_id: int, resume_data: ResumeCreate
    ) -> Resume:
        """Create a new draft resume with initial document."""
        document_id = str(uuid4())
        content_hash = DocumentRepository._calculate_content_hash(resume_data.content)

        document = Document(
            id=document_id,
            root_id=document_id,
            parent_id=None,
            format=resume_data.format,
            content=resume_data.content,
            content_hash=content_hash,
            change_comments="Initial version",
            extra_metadata={},
            created_by=user_id,
        )
        await DocumentRepository.create(db, document)

        resume = Resume(
            id=str(uuid4()),
            user_id=user_id,
            document_id=document_id,
            title=resume_data.title,
            is_draft=True,
            is_deleted=False,
        )
        db.add(resume)

        await db.commit()
        await db.refresh(resume)
        await db.refresh(document)

        resume.document = document
        return resume

    @staticmethod
    async def get_user_resumes(
        db: AsyncSession, user_id: int, include_deleted: bool = False
    ) -> list[Resume]:
        """Get all resumes for a user."""
        query = (
            select(Resume)
            .where(Resume.user_id == user_id)
            .options(selectinload(Resume.document))
            .order_by(Resume.updated_at.desc())
        )

        if not include_deleted:
            query = query.where(Resume.is_deleted == False)

        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get_resume_by_id(
        db: AsyncSession, resume_id: str, user_id: int
    ) -> Optional[Resume]:
        """Get resume by ID (with ownership check)."""
        query = (
            select(Resume)
            .where(
                and_(
                    Resume.id == resume_id,
                    Resume.user_id == user_id,
                    Resume.is_deleted == False,
                )
            )
            .options(selectinload(Resume.document))
        )

        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def update_resume(
        db: AsyncSession, resume_id: str, user_id: int, update_data: ResumeUpdate
    ) -> Resume:
        """Update resume content (creates new document version)."""
        resume = await ResumeService.get_resume_by_id(db, resume_id, user_id)
        if not resume:
            raise NotFoundError("Resume not found")

        current_doc = resume.document
        previous_hash = current_doc.content_hash if current_doc else None

        new_document = await DocumentRepository.create_new_version(
            db=db,
            parent_document=current_doc,
            content=update_data.content,
            created_by=user_id,
            change_comments=update_data.change_comments or "Content updated",
        )
        # Hash availability for changed check
        content_hash = new_document.content_hash

        resume.document_id = new_document.id
        db.add(resume)

        await ResumeService._trigger_analysis_if_needed(
            db,
            resume,
            user_id,
            previous_content_hash=previous_hash,
            new_content_hash=content_hash,
        )
        await db.commit()
        await db.refresh(resume)
        await db.refresh(new_document)

        resume.document = new_document
        return resume

    @staticmethod
    async def update_resume_title(
        db: AsyncSession, resume_id: str, user_id: int, new_title: str
    ) -> Resume:
        """Update resume title (metadata only, no new document version)."""
        resume = await ResumeService.get_resume_by_id(db, resume_id, user_id)
        if not resume:
            raise NotFoundError("Resume not found")

        resume.title = new_title
        db.add(resume)
        await db.commit()
        await db.refresh(resume)

        return resume

    @staticmethod
    async def finalize_resume(db: AsyncSession, resume_id: str, user_id: int) -> Resume:
        """Mark resume as formal version (finalize from draft)."""
        resume = await ResumeService.get_resume_by_id(db, resume_id, user_id)
        if not resume:
            raise NotFoundError("Resume not found")

        can_create, current_count = await ResumeService.check_formal_resume_limit(
            db, user_id
        )
        if not can_create:
            raise BusinessError(
                f"Formal resume limit ({settings.USER_FORMAL_RESUME_LIMIT}) exceeded. Current count: {current_count}",
                response_code=ResponseCode.RESUME_LIMIT_EXCEEDED,
            )

        resume.is_draft = False
        db.add(resume)
        await ResumeService._trigger_analysis_if_needed(db, resume, user_id)
        await db.commit()
        await db.refresh(resume)

        return resume

    @staticmethod
    async def delete_resume(db: AsyncSession, resume_id: str, user_id: int) -> Resume:
        """Soft delete a resume."""
        resume = await ResumeService.get_resume_by_id(db, resume_id, user_id)
        if not resume:
            raise NotFoundError("Resume not found")

        # Remember if this is a formal resume before deletion
        was_formal = not resume.is_draft

        resume.is_deleted = True
        resume.deleted_at = datetime.utcnow()
        db.add(resume)
        await db.commit()
        await db.refresh(resume)

        # Trigger skill aggregation if this was a formal resume
        # (CASCADE will auto-delete resume_skills, aggregation will recalculate user skills)
        if was_formal:
            await TaskService.submit_task(
                db=db,
                spec=TaskSubmissionSpec(
                    task_type=TaskType.SKILL_AGGREGATION,
                    entity_id=resume_id,
                    user_id=user_id,
                    input_data={
                        "user_id": user_id,
                        "resume_id": resume_id,
                    },
                ),
            )
            await db.commit()

        return resume

    @staticmethod
    async def check_formal_resume_limit(db: AsyncSession, user_id: int) -> tuple[bool, int]:
        """Check if user can create more formal resumes."""
        query = (
            select(func.count())
            .select_from(Resume)
            .where(
                and_(
                    Resume.user_id == user_id,
                    Resume.is_draft == False,
                    Resume.is_deleted == False,
                )
            )
        )

        result = await db.execute(query)
        current_count = result.scalar_one()

        can_create_more = current_count < settings.USER_FORMAL_RESUME_LIMIT

        return can_create_more, current_count

    @staticmethod
    async def _trigger_analysis_if_needed(
        db: AsyncSession,
        resume: Resume,
        user_id: int,
        *,
        previous_content_hash: str | None = None,
        new_content_hash: str | None = None,
    ) -> None:
        """Trigger resume analysis workflow if needed."""
        if resume.is_draft:
            return

        content_changed = (
            previous_content_hash
            and new_content_hash
            and previous_content_hash != new_content_hash
        )

        should_analyze = (
            resume.analysis_result is None
            or resume.analyzed_at is None
            or content_changed
        )

        if not should_analyze:
            return

        await TaskService.submit_sequential_tasks(
            db=db,
            entity_type="resume",
            entity_id=resume.id,
            user_id=user_id,
            tasks=[
                TaskSubmissionSpec(
                    task_type=TaskType.RESUME_ANALYSIS,
                    input_data={"resume_id": resume.id},
                ),
                TaskSubmissionSpec(
                    task_type=TaskType.USER_JOB_MATCHING,
                    input_data={"resume_id": resume.id, "user_id": user_id, "days": 30},
                ),
            ],
        )

    @staticmethod
    async def get_resume_versions(
        db: AsyncSession, resume_id: str, user_id: int
    ) -> list[Document]:
        """Get all document versions for a resume."""
        resume = await ResumeService.get_resume_by_id(db, resume_id, user_id)
        if not resume:
            raise NotFoundError("Resume not found")

        root_id = resume.document.root_id

        query = (
            select(Document)
            .where(Document.root_id == root_id)
            .order_by(Document.created_at.desc())
        )

        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def trigger_resume_analysis(
        db: AsyncSession, resume_id: str, user_id: int, manual_trigger: bool = False
    ):
        """Manually trigger resume analysis workflow."""
        resume = await ResumeRepository.get_by_id(db, resume_id)
        if not resume or resume.user_id != user_id:
            raise NotFoundError("Resume not found")

        tasks = [
            TaskSubmissionSpec(
                task_type=TaskType.RESUME_ANALYSIS,
                input_data={"resume_id": resume_id, "manual_trigger": manual_trigger},
            ),
            TaskSubmissionSpec(
                task_type=TaskType.USER_JOB_MATCHING,
                input_data={"resume_id": resume_id, "user_id": user_id, "days": 30},
            ),
        ]

        created_tasks = await TaskService.submit_sequential_tasks(
            db=db,
            entity_type="resume",
            entity_id=resume_id,
            user_id=user_id,
            tasks=tasks,
        )

        await db.commit()
        return created_tasks[0].workflow_id

    @staticmethod
    async def get_resume_analysis(
        db: AsyncSession, resume_id: str, user_id: int
    ) -> Resume:
        """Fetch resume analysis after ownership validation."""
        resume = await ResumeRepository.get_with_document(db, resume_id)
        if not resume or resume.user_id != user_id:
            raise NotFoundError("Resume not found")

        if not resume.analysis_result:
            raise NotFoundError("Analysis not found. Please trigger analysis first.")

        return resume

    @staticmethod
    async def export_resume_to_pdf(
        db: AsyncSession,
        resume_id: str,
        user_id: int,
        template: Optional[str] = None,
        font_size: int = 12,
        include_metadata: bool = False,
    ) -> tuple[bytes, str, str]:
        """Export resume to PDF."""
        from app.modules.resumes.export import DocumentExportService

        resume = await ResumeService.get_resume_by_id(db, resume_id, user_id)
        if not resume:
            raise NotFoundError("Resume not found")

        try:
            pdf_bytes, filename, template_used = DocumentExportService.export_to_pdf(
                document_type="resume",
                content=resume.document.content,
                title=resume.title,
                template=template,
                font_size=font_size,
                include_metadata=include_metadata,
            )

            return pdf_bytes, filename, template_used

        except ValueError as exc:
            raise BadRequestError(str(exc))
        except Exception as exc:  # pragma: no cover - defensive
            raise JobPilotException(str(exc))

    @staticmethod
    async def update_resume_skills(
        db: AsyncSession,
        resume_id: str,
        user_id: int,
        skills: list[dict]
    ) -> tuple[int, int]:
        """
        Save or update skills for a resume.

        This function:
        1. For each skill in the list, INSERT or UPDATE resume_skills
        2. Delete skills that no longer exist in the new list
        3. Does NOT commit - caller should commit

        Args:
            db: Database session
            resume_id: Resume ID
            user_id: User ID
            skills: List of skills [{"name": "Python", "proficiency": "expert"}, ...]

        Returns:
            Number of skills saved
        """
        # Step 1 & 2: Insert or update each skill
        skill_names_in_list = set()
        for skill_data in skills:
            skill_name = skill_data.get("name", "").strip()
            if not skill_name:
                continue

            proficiency_str = skill_data.get(
                "proficiency", ProficiencyLevel.INTERMEDIATE.value).lower()

            skill_names_in_list.add(skill_name)

            # Map proficiency string to enum
            try:
                proficiency = ProficiencyLevel(proficiency_str)
            except ValueError:
                proficiency = ProficiencyLevel.INTERMEDIATE

            # Check if skill already exists
            stmt = select(ResumeSkill).where(
                ResumeSkill.resume_id == resume_id,
                ResumeSkill.skill_name == skill_name
            )
            existing_skill = (await db.execute(stmt)).scalar_one_or_none()

            if existing_skill:
                # Update existing skill
                existing_skill.proficiency_level = proficiency
                existing_skill.updated_at = datetime.now()
            else:
                # Insert new skill
                new_skill = ResumeSkill(
                    id=str(uuid4()),
                    user_id=user_id,
                    resume_id=resume_id,
                    skill_name=skill_name,
                    proficiency_level=proficiency,
                    extracted_from=skill_data.get("extracted_from")
                )
                db.add(new_skill)

        # Step 3: Delete skills that no longer exist in the new list
        if skill_names_in_list:
            from sqlalchemy import delete
            stmt = delete(ResumeSkill).where(
                ResumeSkill.resume_id == resume_id,
                ResumeSkill.skill_name.notin_(skill_names_in_list)
            )
            deleted_skills = (await db.execute(stmt)).rowcount
        else:
            # All skills removed, delete all
            from sqlalchemy import delete
            stmt = delete(ResumeSkill).where(ResumeSkill.resume_id == resume_id)
            deleted_skills = (await db.execute(stmt)).rowcount

        return len(skill_names_in_list), deleted_skills
