"""User-related models."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import String, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.base_model import Base, TimestampMixin
from app.shared.enums import ProficiencyLevel


class UserSkill(Base, TimestampMixin):
    """Standardized user skill with proficiency."""

    __tablename__ = "user_skills"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    skill_name: Mapped[str] = mapped_column(String(200), nullable=False)
    proficiency: Mapped[ProficiencyLevel] = mapped_column(String(20), nullable=False)
    skill_type: Mapped[str] = mapped_column(String(50), nullable=False, default="technical")
    extracted_from_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Optional metadata container
    extra_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="skills")

    def promote(self, new_level: ProficiencyLevel):
        """Upgrade proficiency and touch updated_at."""
        self.proficiency = new_level
        self.updated_at = datetime.now(timezone.utc)
