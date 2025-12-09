"""
Resume service layer - business logic for resume operations.
"""
import hashlib
from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, status

from app.modules.resumes.models import Resume, Document, DocumentFormat
from app.modules.resumes.schemas import ResumeCreate, ResumeUpdate
from app.modules.resumes.repository import ResumeRepository
from app.modules.workflow.service import WorkflowService
from app.shared.enums import WorkflowType, TaskType


# Global configuration for formal resume limit (can be moved to config later)
FORMAL_RESUME_LIMIT = 3


class ResumeService:
    """Service class for Resume-related operations"""

    @staticmethod
    def _calculate_content_hash(content: str) -> str:
        """Calculate SHA-256 hash of content for deduplication"""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    @staticmethod
    async def create_resume(
        db: AsyncSession,
        user_id: int,
        resume_data: ResumeCreate
    ) -> Resume:
        """
        Create a new draft resume with initial document.

        Args:
            db: Database session
            user_id: User ID
            resume_data: Resume creation data

        Returns:
            Created Resume instance
        """
        # Create initial document
        document_id = str(uuid4())
        content_hash = ResumeService._calculate_content_hash(
            resume_data.content)

        document = Document(
            id=document_id,
            root_id=document_id,  # First version, self-reference
            parent_id=None,
            format=resume_data.format,
            content=resume_data.content,
            content_hash=content_hash,
            change_comments="Initial version",
            extra_metadata={},
            created_by=user_id
        )
        db.add(document)

        # Create resume metadata
        resume = Resume(
            id=str(uuid4()),
            user_id=user_id,
            document_id=document_id,
            title=resume_data.title,
            is_draft=True,
            is_deleted=False
        )
        db.add(resume)

        await db.commit()
        await db.refresh(resume)
        await db.refresh(document)

        # Load relationship
        resume.document = document

        return resume

    @staticmethod
    async def get_user_resumes(
        db: AsyncSession,
        user_id: int,
        include_deleted: bool = False
    ) -> list[Resume]:
        """
        Get all resumes for a user.

        Args:
            db: Database session
            user_id: User ID
            include_deleted: Whether to include soft-deleted resumes

        Returns:
            List of Resume instances
        """
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
        db: AsyncSession,
        resume_id: str,
        user_id: int
    ) -> Optional[Resume]:
        """
        Get resume by ID (with ownership check).

        Args:
            db: Database session
            resume_id: Resume ID
            user_id: User ID (for ownership verification)

        Returns:
            Resume instance or None
        """
        query = (
            select(Resume)
            .where(
                and_(
                    Resume.id == resume_id,
                    Resume.user_id == user_id,
                    Resume.is_deleted == False
                )
            )
            .options(selectinload(Resume.document))
        )

        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def update_resume(
        db: AsyncSession,
        resume_id: str,
        user_id: int,
        update_data: ResumeUpdate
    ) -> Resume:
        """
        Update resume content (creates new document version).

        Args:
            db: Database session
            resume_id: Resume ID
            user_id: User ID
            update_data: Update data

        Returns:
            Updated Resume instance

        Raises:
            HTTPException: If resume not found or not editable
        """
        # Get existing resume
        resume = await ResumeService.get_resume_by_id(db, resume_id, user_id)
        if not resume:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resume not found"
            )

        # Get current document
        current_doc = resume.document
        previous_hash = current_doc.content_hash if current_doc else None

        # Create new document version
        new_doc_id = str(uuid4())
        content_hash = ResumeService._calculate_content_hash(
            update_data.content)

        new_document = Document(
            id=new_doc_id,
            root_id=current_doc.root_id,  # Same family
            parent_id=current_doc.id,  # Points to previous version
            format=current_doc.format,
            content=update_data.content,
            content_hash=content_hash,
            change_comments=update_data.change_comments or "Content updated",
            extra_metadata=current_doc.extra_metadata or {},
            created_by=user_id
        )
        db.add(new_document)

        # Update resume to point to new document
        resume.document_id = new_doc_id
        db.add(resume)

        # Trigger analysis if formal resume and content changed/new
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
        db: AsyncSession,
        resume_id: str,
        user_id: int,
        new_title: str
    ) -> Resume:
        """
        Update resume title (metadata only, doesn't create new document version).

        Args:
            db: Database session
            resume_id: Resume ID
            user_id: User ID
            new_title: New title

        Returns:
            Updated Resume instance
        """
        resume = await ResumeService.get_resume_by_id(db, resume_id, user_id)
        if not resume:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resume not found"
            )

        resume.title = new_title
        db.add(resume)
        await db.commit()
        await db.refresh(resume)

        return resume

    @staticmethod
    async def finalize_resume(
        db: AsyncSession,
        resume_id: str,
        user_id: int
    ) -> Resume:
        """
        Mark resume as formal version (finalize from draft).

        Args:
            db: Database session
            resume_id: Resume ID
            user_id: User ID

        Returns:
            Updated Resume instance

        Raises:
            HTTPException: If resume not found or limit exceeded
        """
        resume = await ResumeService.get_resume_by_id(db, resume_id, user_id)
        if not resume:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resume not found"
            )

        # Check formal resume limit
        can_create, current_count = await ResumeService.check_formal_resume_limit(db, user_id)
        if not can_create:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Formal resume limit ({FORMAL_RESUME_LIMIT}) exceeded. Current count: {current_count}"
            )

        resume.is_draft = False
        db.add(resume)
        await ResumeService._trigger_analysis_if_needed(db, resume, user_id)
        await db.commit()
        await db.refresh(resume)

        return resume

    @staticmethod
    async def delete_resume(
        db: AsyncSession,
        resume_id: str,
        user_id: int
    ) -> Resume:
        """
        Soft delete a resume.

        Args:
            db: Database session
            resume_id: Resume ID
            user_id: User ID

        Returns:
            Deleted Resume instance

        Raises:
            HTTPException: If resume not found
        """
        resume = await ResumeService.get_resume_by_id(db, resume_id, user_id)
        if not resume:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resume not found"
            )

        resume.is_deleted = True
        resume.deleted_at = datetime.utcnow()
        db.add(resume)
        await db.commit()
        await db.refresh(resume)

        return resume

    @staticmethod
    async def check_formal_resume_limit(
        db: AsyncSession,
        user_id: int
    ) -> tuple[bool, int]:
        """
        Check if user can create more formal resumes.

        Args:
            db: Database session
            user_id: User ID

        Returns:
            Tuple of (can_create_more, current_count)
        """
        query = (
            select(func.count())
            .select_from(Resume)
            .where(
                and_(
                    Resume.user_id == user_id,
                    Resume.is_draft == False,
                    Resume.is_deleted == False
                )
            )
        )

        result = await db.execute(query)
        current_count = result.scalar_one()

        can_create_more = current_count < FORMAL_RESUME_LIMIT

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
        """
        Trigger resume analysis workflow if needed.

        Conditions:
        - Resume is formal (not draft)
        - Never analyzed OR analyzed_at missing OR content hash changed
        """
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

        workflow = await WorkflowService.create_workflow(
            db=db,
            workflow_type=WorkflowType.RESUME_ANALYSIS,
            user_id=user_id,
            entity_id=resume.id,
            input_data={"resume_id": resume.id},
        )

        await WorkflowService.submit_task(
            db=db,
            workflow_id=workflow.id,
            task_type=TaskType.RESUME_ANALYSIS,
            input_data={"resume_id": resume.id},
            resume_id=resume.id,
        )
        await WorkflowService.submit_task(
            db=db,
            workflow_id=workflow.id,
            task_type=TaskType.MATCH_USER_JOBS,
            input_data={"resume_id": resume.id,
                        "user_id": user_id, "days": 30},
            user_id=user_id,
            days=30,
        )

    @staticmethod
    async def get_resume_versions(
        db: AsyncSession,
        resume_id: str,
        user_id: int
    ) -> list[Document]:
        """
        Get all document versions for a resume.

        Args:
            db: Database session
            resume_id: Resume ID
            user_id: User ID

        Returns:
            List of Document versions (ordered by created_at desc)
        """
        resume = await ResumeService.get_resume_by_id(db, resume_id, user_id)
        if not resume:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resume not found"
            )

        root_id = resume.document.root_id

        # Get all documents in the same family
        query = (
            select(Document)
            .where(Document.root_id == root_id)
            .order_by(Document.created_at.desc())
        )

        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def trigger_resume_analysis(
        db: AsyncSession,
        resume_id: str,
        user_id: int,
        manual_trigger: bool = False,
    ):
        """
        Manually trigger resume analysis workflow.

        Always creates a new workflow/task after ownership validation.
        """
        resume = await ResumeRepository.get_by_id(db, resume_id)
        if not resume or resume.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resume not found"
            )

        workflow = await WorkflowService.create_workflow(
            db=db,
            workflow_type=WorkflowType.RESUME_ANALYSIS,
            user_id=user_id,
            entity_id=resume_id,
            input_data={"resume_id": resume_id,
                        "manual_trigger": manual_trigger},
        )

        resume_task, _ = await WorkflowService.submit_task(
            db=db,
            workflow_id=workflow.id,
            task_type=TaskType.RESUME_ANALYSIS,
            input_data={"resume_id": resume_id},
            resume_id=resume_id,
        )
        # Enqueue matching task dependent on resume analysis
        await WorkflowService.submit_task(
            db=db,
            workflow_id=workflow.id,
            task_type=TaskType.MATCH_USER_JOBS,
            input_data={"resume_id": resume_id,
                        "user_id": user_id, "days": 30},
            depends_on=[resume_task.id],
            user_id=user_id,
            days=30,
        )

        await db.commit()
        return workflow

    @staticmethod
    async def get_resume_analysis(
        db: AsyncSession,
        resume_id: str,
        user_id: int,
    ) -> Resume:
        """
        Fetch resume analysis after ownership validation.
        """
        resume = await ResumeRepository.get_with_document(db, resume_id)
        if not resume or resume.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resume not found"
            )

        if not resume.analysis_result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Analysis not found. Please trigger analysis first."
            )

        return resume

    @staticmethod
    async def export_resume_to_pdf(
        db: AsyncSession,
        resume_id: str,
        user_id: int,
        template: Optional[str] = None,
        font_size: int = 12,
        include_metadata: bool = False
    ) -> tuple[bytes, str, str]:
        """
        Export resume to PDF.

        Args:
            db: Database session
            resume_id: Resume ID
            user_id: User ID
            template: Template name (modern/classic/minimal)
            font_size: Base font size in pt
            include_metadata: Include generation timestamp

        Returns:
            Tuple of (pdf_bytes, filename, template_used)

        Raises:
            HTTPException: If resume not found or export fails
        """
        from app.modules.resumes.export import DocumentExportService

        # Get resume
        resume = await ResumeService.get_resume_by_id(db, resume_id, user_id)
        if not resume:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resume not found"
            )

        # Export using universal service
        try:
            pdf_bytes, filename, template_used = DocumentExportService.export_to_pdf(
                document_type="resume",
                content=resume.document.content,
                title=resume.title,
                template=template,
                font_size=font_size,
                include_metadata=include_metadata
            )

            return pdf_bytes, filename, template_used

        except ValueError as e:
            # Template validation errors
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to generate PDF: {str(e)}"
            )
