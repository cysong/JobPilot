"""User authentication models"""
from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.base_model import Base, TimestampMixin
from app.shared.enums import Role

if TYPE_CHECKING:
    from app.modules.resumes.models import Resume, Document
    from app.modules.users.models import UserSkill


class SecurityTokenType(str, Enum):
    """Supported one-time security token types."""

    EMAIL_VERIFY = "EMAIL_VERIFY"
    PASSWORD_RESET = "PASSWORD_RESET"
    EMAIL_CHANGE = "EMAIL_CHANGE"


class User(Base, TimestampMixin):
    """User account model"""

    __tablename__ = "users"

    # Primary Key
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Authentication
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
        comment="User email address (unique identifier)"
    )
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Bcrypt hashed password"
    )

    # Profile
    full_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="User full name"
    )

    # Role & Permissions
    role: Mapped[Role] = mapped_column(
        String(20),
        nullable=False,
        default=Role.USER,
        comment="User role (USER/VIP/ADMIN)"
    )

    # Status
    is_active: Mapped[bool] = mapped_column(
        default=True,
        nullable=False,
        comment="Whether user account is active"
    )
    email_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when current email was verified"
    )
    password_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp of the latest successful password change"
    )
    preferences: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
        comment="User job-search preferences"
    )

    # Relationships
    resumes: Mapped[list["Resume"]] = relationship("Resume", back_populates="user", cascade="all, delete-orphan")
    created_documents: Mapped[list["Document"]] = relationship("Document", back_populates="creator", foreign_keys="Document.created_by")
    skills: Mapped[list["UserSkill"]] = relationship("UserSkill", back_populates="user", cascade="all, delete-orphan")
    security_tokens: Mapped[list["UserSecurityToken"]] = relationship(
        "UserSecurityToken",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    # Indexes
    __table_args__ = (
        Index("ix_users_role", "role"),
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email='{self.email}', role='{self.role}')>"


class UserSecurityToken(Base):
    """One-time token used by account-security flows."""

    __tablename__ = "user_security_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(Text, nullable=False)
    token_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    user: Mapped["User"] = relationship("User", back_populates="security_tokens")

    __table_args__ = (
        Index("idx_user_security_tokens_user_type", "user_id", "token_type"),
        Index("idx_user_security_tokens_expires_at", "expires_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<UserSecurityToken(id={self.id}, user_id={self.user_id}, "
            f"token_type='{self.token_type}')>"
        )
