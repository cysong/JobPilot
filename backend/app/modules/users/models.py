"""User-related models."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import String, Boolean, DateTime, ForeignKey, JSON, BigInteger, Integer, Index, UniqueConstraint, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional

from app.shared.base_model import Base, TimestampMixin
from app.shared.enums import ProficiencyLevel


class UserSkill(Base, TimestampMixin):
    """
    User skill model (aggregated and deduplicated).

    Stores the final deduplicated skill list for each user.
    Skills can come from resume analysis or manual input.
    """
    __tablename__ = "user_skills"

    # Primary key
    id: Mapped[str] = mapped_column(String(255), primary_key=True)

    # Foreign key
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Skill data
    skill_name: Mapped[str] = mapped_column(String(100), nullable=False)
    proficiency_level: Mapped[ProficiencyLevel] = mapped_column(SQLEnum(ProficiencyLevel, native_enum=False), nullable=False)

    # Manual management flags
    is_manual: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, comment="Whether manually edited by user")
    manual_proficiency: Mapped[Optional[ProficiencyLevel]] = mapped_column(SQLEnum(ProficiencyLevel, native_enum=False), nullable=True, comment="User-set proficiency if manually edited")

    # Metadata
    source_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="How many resumes mention this skill")
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, comment="Last time this skill appeared in a resume")

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="skills", foreign_keys=[user_id])

    # Table constraints
    __table_args__ = (
        UniqueConstraint("user_id", "skill_name", name="uk_user_skill"),
        Index("idx_user_skills_proficiency", "user_id", "proficiency_level"),
        Index("idx_user_skills_manual", "user_id", "is_manual"),
    )

    def __repr__(self):
        return f"<UserSkill(id={self.id}, user_id={self.user_id}, skill={self.skill_name}, level={self.proficiency_level}, manual={self.is_manual})>"
