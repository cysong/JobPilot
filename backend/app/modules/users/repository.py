"""Repository layer for user skills."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.models import UserSkill
from app.shared.enums import ProficiencyLevel
from app.shared.utils import generate_id


class UserSkillRepository:
    """Upsert operations for user skills."""

    @staticmethod
    async def upsert_from_resume_analysis(
        db: AsyncSession,
        user_id: int,
        skills: list[dict],
        resume_id: str,
    ):
        """
        Upsert skills from resume analysis.

        Rules:
        - New skill: Create
        - Existing skill: Only update if new proficiency is higher
        """
        proficiency_order = {
            ProficiencyLevel.BEGINNER: 1,
            ProficiencyLevel.INTERMEDIATE: 2,
            ProficiencyLevel.ADVANCED: 3,
            ProficiencyLevel.EXPERT: 4,
        }

        for skill_data in skills:
            existing = await db.execute(
                select(UserSkill).where(
                    UserSkill.user_id == user_id,
                    UserSkill.skill_name == skill_data["name"]
                )
            )
            existing_skill = existing.scalar_one_or_none()

            new_proficiency = ProficiencyLevel(skill_data["proficiency"])

            if not existing_skill:
                new_skill = UserSkill(
                    id=generate_id("usk"),
                    user_id=user_id,
                    skill_name=skill_data["name"],
                    proficiency=new_proficiency,
                    skill_type="technical",
                    extracted_from_id=resume_id,
                    extra_metadata={"source": "resume_analysis"},
                )
                db.add(new_skill)
            else:
                if proficiency_order[new_proficiency] > proficiency_order[existing_skill.proficiency]:
                    existing_skill.promote(new_proficiency)
                    existing_skill.extracted_from_id = resume_id
                    existing_skill.extra_metadata = {"source": "resume_analysis"}
