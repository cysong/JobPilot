"""
Resume service layer - business logic for resume operations.
"""
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette.concurrency import run_in_threadpool

from app.core.exceptions import (
    BadRequestError,
    BusinessError,
    ForbiddenError,
    JobPilotException,
    NotFoundError,
)
from app.core.response_codes import ResponseCode
from app.modules.resumes.models import Document, Resume, ResumeSkill
from app.modules.resumes.repository import ResumeRepository, DocumentRepository
from app.modules.resumes.schemas import (
    ResumeCreate,
    ResumeUpdate,
)
from app.modules.workflow.service import TaskService, TaskSubmissionSpec
from app.shared.enums import Role, TaskType, ProficiencyLevel
from app.core.config import settings
from app.modules.workflow import TaskExecution
from app.shared.schemas import DocumentEditResponse, DocumentUpdateRequest
from app.shared.skills import (
    canonical_skill_name,
    highest_proficiency,
    proficiency_rank,
    skill_key,
    to_proficiency,
)



class ResumeService:
    """Service class for Resume-related operations."""

    @staticmethod
    def get_formal_resume_limit(role: Role) -> int | None:
        """Return the formal resume limit for the given user role."""
        if role == Role.ADMIN:
            return None
        if role == Role.VIP:
            return settings.VIP_FORMAL_RESUME_LIMIT
        return settings.USER_FORMAL_RESUME_LIMIT

    @staticmethod
    async def get_resume_for_edit(
        db: AsyncSession, resume_id: str, user_id: int
    ) -> DocumentEditResponse:
        """Get resume data for editing, returned as unified DocumentEditResponse."""
        resume = await ResumeRepository.get_with_document(db, resume_id)
        if not resume:
            raise NotFoundError("Resume not found")
        if resume.user_id != user_id:
            raise ForbiddenError("You don't have permission to edit this resume")

        document = resume.document
        return DocumentEditResponse(
            business_type="resume",
            business_id=resume.id,
            title=resume.title,
            document_id=document.id,
            content=document.content,
            format=document.format,
            created_at=resume.created_at,
            updated_at=resume.updated_at,
            is_draft=resume.is_draft,
        )

    @staticmethod
    async def update_resume_content(
        db: AsyncSession,
        resume_id: str,
        user_id: int,
        payload: DocumentUpdateRequest,
    ) -> Resume:
        """Update resume content by creating a new document version and relinking."""
        resume = await ResumeRepository.get_with_document(db, resume_id)
        if not resume:
            raise NotFoundError("Resume not found")
        if resume.user_id != user_id:
            raise ForbiddenError("You don't have permission to edit this resume")

        current_doc = resume.document
        if not current_doc:
            raise NotFoundError("Document not found")
        previous_hash = current_doc.content_hash if current_doc else None

        new_document = await DocumentRepository.create_new_version(
            db=db,
            parent_document=current_doc,
            content=payload.content,
            created_by=user_id,
            change_comments=payload.change_comments or "Content updated",
        )

        resume.document_id = new_document.id
        resume.updated_at = datetime.now(timezone.utc)
        db.add(resume)

        await ResumeService._trigger_analysis_if_needed(
            db,
            resume,
            user_id,
            previous_content_hash=previous_hash,
            new_content_hash=new_document.content_hash,
        )

        await db.commit()
        await db.refresh(resume)
        await db.refresh(new_document)
        resume.document = new_document

        return resume

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
            query = query.where(Resume.is_deleted.is_(False))

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
                    Resume.is_deleted.is_(False),
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
    async def finalize_resume(
        db: AsyncSession,
        resume_id: str,
        user_id: int,
        role: Role,
    ) -> Resume:
        """Mark resume as formal version (finalize from draft)."""
        resume = await ResumeService.get_resume_by_id(db, resume_id, user_id)
        if not resume:
            raise NotFoundError("Resume not found")

        can_create, current_count, limit = await ResumeService.check_formal_resume_limit(
            db, user_id, role
        )
        if not can_create:
            raise BusinessError(
                f"Formal resume limit ({limit}) exceeded. Current count: {current_count}",
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
        resume.deleted_at = datetime.now(timezone.utc)
        db.add(resume)
        await db.commit()
        await db.refresh(resume)

        # Trigger skill aggregation if this was a formal resume
        # (CASCADE will auto-delete resume_skills, aggregation will recalculate user skills)
        if was_formal:
            await TaskService.submit_task(
                db=db,
                task_type=TaskType.SKILL_AGGREGATION,
                entity_id=resume_id,
                user_id=user_id,
                input_data={
                    "user_id": user_id,
                    "resume_id": resume_id,
                },
            )
            await db.commit()

        return resume

    @staticmethod
    async def check_formal_resume_limit(
        db: AsyncSession,
        user_id: int,
        role: Role,
    ) -> tuple[bool, int, int | None]:
        """Check if user can create more formal resumes."""
        query = (
            select(func.count())
            .select_from(Resume)
            .where(
                and_(
                    Resume.user_id == user_id,
                    Resume.is_draft.is_(False),
                    Resume.is_deleted.is_(False),
                )
            )
        )

        result = await db.execute(query)
        current_count = result.scalar_one()

        limit = ResumeService.get_formal_resume_limit(role)
        can_create_more = limit is None or current_count < limit

        return can_create_more, current_count, limit

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

        await ResumeService._submit_resume_analysis_tasks(db, resume.id, user_id)

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

        created_tasks = await ResumeService._submit_resume_analysis_tasks(db, resume_id, user_id)
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
            pdf_bytes, filename, template_used = await run_in_threadpool(
                DocumentExportService.export_to_pdf,
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
    def normalize_resume_skills(skills: list[dict]) -> dict[str, dict]:
        """Clean one resume's LLM skill list, keyed by ``skill_key``.

        - Names are canonicalised, so aliases and casing variants collapse.
        - Duplicates within the list keep the highest level and all evidence.
        - Unknown levels fall back to INTERMEDIATE.
        - A skill with no evidence outside a skills list (``extracted_from``
          empty) is capped at INTERMEDIATE: listing a tool is not proof of
          advanced use.
        """
        normalized: dict[str, dict] = {}
        for skill_data in skills:
            raw_name = (skill_data.get("name") or "").strip()
            if not raw_name:
                continue
            name = canonical_skill_name(raw_name)
            key = skill_key(name)
            if not key:
                continue

            proficiency = to_proficiency(skill_data.get("proficiency")) or ProficiencyLevel.INTERMEDIATE
            extracted_from = list(skill_data.get("extracted_from") or [])

            current = normalized.get(key)
            if current is None:
                normalized[key] = {"name": name, "proficiency": proficiency, "extracted_from": extracted_from}
                continue
            current["proficiency"] = highest_proficiency([current["proficiency"], proficiency])
            current["extracted_from"].extend(extracted_from)

        for entry in normalized.values():
            if not entry["extracted_from"] and proficiency_rank(entry["proficiency"]) > proficiency_rank(
                ProficiencyLevel.INTERMEDIATE
            ):
                entry["proficiency"] = ProficiencyLevel.INTERMEDIATE
            entry["extracted_from"] = entry["extracted_from"] or None
        return normalized

    @staticmethod
    async def update_resume_skills(
        db: AsyncSession,
        resume_id: str,
        user_id: int,
        skills: list[dict]
    ) -> tuple[int, int]:
        """
        Replace a resume's skills with the given LLM output.

        Skills are matched to existing rows by ``skill_key`` (so a re-analysis
        that changes "pytest" to "Pytest" updates the row instead of adding a
        second one), existing duplicates of one skill are collapsed, and rows
        for skills no longer listed are deleted. Does NOT commit.

        Args:
            db: Database session
            resume_id: Resume ID
            user_id: User ID
            skills: List of skills [{"name": "Python", "proficiency": "expert", "extracted_from": [...]}, ...]

        Returns:
            (number of skills kept, number of rows deleted)
        """
        normalized = ResumeService.normalize_resume_skills(skills)

        existing_rows = (await db.execute(
            select(ResumeSkill).where(ResumeSkill.resume_id == resume_id)
        )).scalars().all()

        keeper_by_key: dict[str, ResumeSkill] = {}
        to_delete: list[ResumeSkill] = []
        for row in existing_rows:
            key = skill_key(row.skill_name)
            if key in normalized and key not in keeper_by_key:
                keeper_by_key[key] = row
            else:
                to_delete.append(row)

        # Delete first so renames below cannot collide on uk_resume_skill.
        for row in to_delete:
            await db.delete(row)
        if to_delete:
            await db.flush()

        now = datetime.now(timezone.utc)
        for key, entry in normalized.items():
            row = keeper_by_key.get(key)
            if row is not None:
                row.skill_name = entry["name"]
                row.proficiency_level = entry["proficiency"]
                row.extracted_from = entry["extracted_from"]
                row.updated_at = now
            else:
                db.add(ResumeSkill(
                    id=str(uuid4()),
                    user_id=user_id,
                    resume_id=resume_id,
                    skill_name=entry["name"],
                    proficiency_level=entry["proficiency"],
                    extracted_from=entry["extracted_from"],
                ))

        return len(normalized), len(to_delete)

    @staticmethod
    async def _submit_resume_analysis_tasks(db: AsyncSession, resume_id: str, user_id: int) -> list[TaskExecution]:
        """
        Submit resume analysis workflow tasks.

        Task sequence:
        1. RESUME_ANALYSIS - Analyzes resume, outputs skills_updated/skills_deleted/is_draft
        2. SKILL_AGGREGATION - Conditionally aggregates skills (checks RESUME_ANALYSIS output)
        USER_JOB_MATCHING is temporarily disabled to stop creating new matching jobs.
        """
        return await TaskService.submit_sequential_tasks(
            db=db,
            entity_type="resume",
            entity_id=resume_id,
            user_id=user_id,
            tasks=[
                TaskSubmissionSpec(
                    task_type=TaskType.RESUME_ANALYSIS,
                    entity_id=resume_id,
                    input_data={"resume_id": resume_id},
                ),
                TaskSubmissionSpec(
                    task_type=TaskType.SKILL_AGGREGATION,
                    entity_id=resume_id,
                    input_data={
                        "user_id": user_id,
                        "resume_id": resume_id,
                    },
                )
                # TaskSubmissionSpec(
                #     task_type=TaskType.USER_JOB_MATCHING,
                #     entity_id=str(user_id),  # Convert int to str for entity_id
                #     input_data={"user_id": user_id, "days": 30},  # Remove resume_id - not accepted by task
                # ),
            ],
        )
