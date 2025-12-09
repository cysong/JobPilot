"""
Resume and Document models.

Document uses chained version model:
- rootId: Document family root (first version self-references)
- parentId: Content source (cross-family points to template, same-family points to previous version)
- Supports soft delete for Resume
"""
from datetime import datetime
from typing import Optional
from enum import Enum
from datetime import datetime
from typing import Optional
from enum import Enum

from sqlalchemy import String, Text, Boolean, DateTime, ForeignKey, Enum as SQLEnum, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.base_model import Base, TimestampMixin


class DocumentFormat(str, Enum):
    """Document format types"""
    MARKDOWN = "Markdown"
    HTML = "HTML"
    PLAINTEXT = "PlainText"


class Document(Base, TimestampMixin):
    """
    Document model with chained version support.

    All document content (resumes, cover letters) is stored in this table.
    Version chain is managed through rootId and parentId:
    - rootId: Groups documents in the same family
    - parentId: Tracks content derivation (template source or previous version)
    """
    __tablename__ = "documents"

    # Primary key
    id: Mapped[str] = mapped_column(String(255), primary_key=True)

    # Document family and version tracking
    root_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    parent_id: Mapped[Optional[str]] = mapped_column(String(255), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True, index=True)

    # Content
    format: Mapped[DocumentFormat] = mapped_column(SQLEnum(DocumentFormat, native_enum=False), default=DocumentFormat.MARKDOWN)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)  # SHA-256 hash for deduplication

    # Metadata
    change_comments: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Version change description
    extra_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # JSON field for business-specific data

    # Creator (User.id is int type)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Relationships
    creator: Mapped["User"] = relationship("User", back_populates="created_documents", foreign_keys=[created_by])
    parent: Mapped[Optional["Document"]] = relationship("Document", remote_side="Document.id", foreign_keys=[parent_id], back_populates="children")
    children: Mapped[list["Document"]] = relationship("Document", back_populates="parent", foreign_keys=[parent_id])

    # Business layer relationships (one-to-one with Resume)
    resume: Mapped[Optional["Resume"]] = relationship("Resume", back_populates="document", uselist=False)

    def __repr__(self):
        return f"<Document(id={self.id}, root_id={self.root_id}, format={self.format})>"


class Resume(Base, TimestampMixin):
    """
    Resume metadata model.

    Actual content is stored in Document table.
    Supports draft/formal version workflow and soft delete.
    """
    __tablename__ = "resumes"

    # Primary key
    id: Mapped[str] = mapped_column(String(255), primary_key=True)

    # Basic fields (User.id is int type)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id: Mapped[str] = mapped_column(String(255), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)

    # Status
    is_draft: Mapped[bool] = mapped_column(Boolean, default=True, index=True)  # Draft or formal version

    # Soft delete
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Analysis fields
    target_job_titles: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=True,
        default=list,
        comment="Top recommended job titles from resume analysis (3-5 items)"
    )
    analysis_result: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    analyzed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    analysis_version: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="resumes", foreign_keys=[user_id])
    document: Mapped["Document"] = relationship("Document", back_populates="resume", foreign_keys=[document_id])

    # Applications that use this resume as template
    # applications: Mapped[list["Application"]] = relationship("Application", back_populates="source_resume")

    def __repr__(self):
        return f"<Resume(id={self.id}, title={self.title}, is_draft={self.is_draft})>"
