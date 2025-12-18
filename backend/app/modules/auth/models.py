"""User authentication models"""
from __future__ import annotations
from typing import TYPE_CHECKING
from sqlalchemy import String, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.shared.base_model import Base, TimestampMixin
from app.shared.enums import Role

if TYPE_CHECKING:
    from app.modules.resumes.models import Resume, Document
    from app.modules.users.models import UserSkill


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

    # Relationships
    resumes: Mapped[list["Resume"]] = relationship("Resume", back_populates="user", cascade="all, delete-orphan")
    created_documents: Mapped[list["Document"]] = relationship("Document", back_populates="creator", foreign_keys="Document.created_by")
    skills: Mapped[list["UserSkill"]] = relationship("UserSkill", back_populates="user", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index("ix_users_role", "role"),
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email='{self.email}', role='{self.role}')>"
